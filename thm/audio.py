"""
Audio feature extraction — Section 5 families A, B, C, D, E and G.

Turns one audio file into the dict that `db.save_features` writes and that
`similarity.py` reads back. Every key here maps to a column in db._FEATURE_COLUMNS.

MEASURED vs APPROXIMATED
------------------------
The PRD requires provenance to be recorded, and similarity.py discounts
anything inferred. The line drawn here is:

  measured     — a direct mapping of something we actually computed, with no
                 free parameters and no musical guesswork. Tempo, key, LUFS,
                 spectral shape, MFCC, band balance all qualify.

  approximated — a hand-weighted combination of several signals standing in for
                 a perceptual label we cannot truly measure without a listener
                 study. "Valence" and "danceability" are the honest examples:
                 no amount of signal processing tells you a song is *happy*.

Being wrong about this is not cosmetic. A guessed valence carrying full weight
would let a fabrication outvote a measured tempo in the composite score.

WHY MP3 NEEDS NO ffmpeg HERE
----------------------------
soundfile ships libsndfile >= 1.1, which decodes MP3 natively. Verified against
this library: libsndfile 1.2.2, fmt=MP3. ffmpeg would only be needed for
.m4a/AAC, and this library has none.

Usage (as a library):  from .audio import extract_features
"""

import math

import numpy as np

# librosa is imported lazily inside _librosa() so that the rest of the package
# (lyrics engine, similarity engine, tests) still imports and runs on a machine
# where the heavy audio stack is absent or broken.

_SR = 22050          # analysis rate: standard for music informatics, keeps
                     # MFCC/spectral work cheap and comparable between tracks
_HOP = 512
_N_MFCC = 13
_ENVELOPE_SEGMENTS = 8

# HPSS gets a coarser STFT because it is by far the most expensive step and the
# extra resolution buys nothing: the separation window is what matters, and
# hop * kernel is what defines it. See the note at the call site.
_HPSS_HOP = 1024
_HPSS_KERNEL = 15


def _librosa():
    import librosa
    return librosa


# ---------------------------------------------------------------------------
# Key detection
# ---------------------------------------------------------------------------
# Krumhansl-Schmuckler key-finding: correlate the track's average chroma vector
# against empirically-derived major/minor tonal-hierarchy profiles, rotated to
# every one of the 12 possible tonics. The rotation with the highest Pearson
# correlation wins. This is the standard method and needs no training data.

_PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                      2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                      2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def detect_key(chroma_mean):
    """
    Return (key_note, scale_mode, confidence) from a 12-element chroma vector.

    confidence is the gap between the best and second-best correlation,
    squashed to 0..1 — a track that sits ambiguously between two keys should
    not report a confident key.
    """
    if chroma_mean is None or len(chroma_mean) != 12:
        return None, None, None

    v = np.asarray(chroma_mean, dtype=float)
    if not np.any(v):
        return None, None, None

    # Centre both sides before correlating; Pearson, not raw dot product.
    v = v - v.mean()

    best = (-2.0, None, None)
    scores = []
    for tonic in range(12):
        for mode, profile in (("major", _KS_MAJOR), ("minor", _KS_MINOR)):
            p = np.roll(profile, tonic)
            p = p - p.mean()
            denom = np.linalg.norm(v) * np.linalg.norm(p)
            if denom == 0:
                continue
            r = float(np.dot(v, p) / denom)
            scores.append(((r, tonic, mode)))
            if r > best[0]:
                best = (r, tonic, mode)

    scores.sort(key=lambda s: -s[0])
    if best[1] is None:
        return None, None, None

    # Confidence: how far clear of the runner-up the winner is.
    runner_up = scores[1][0] if len(scores) > 1 else 0.0
    confidence = max(0.0, min(1.0, (best[0] - runner_up) * 4.0))

    return _PITCH_NAMES[best[1]], best[2], round(confidence, 3)


# ---------------------------------------------------------------------------
# Composite / perceptual features (all approximated — see module docstring)
# ---------------------------------------------------------------------------

def _valence(mode, tempo, centroid_hz):
    """
    Approximate musical positivity.

    Major mode reads as brighter than minor; faster and more centred-in-the-
    high-mids reads brighter still. This is a proxy and is labelled as one —
    it is not a measurement of how the music feels.
    """
    mode_term = 0.65 if mode == "major" else 0.35
    tempo_term = max(0.0, min(1.0, (tempo - 60.0) / 100.0))
    bright_term = max(0.0, min(1.0, (centroid_hz - 800.0) / 2600.0))
    return round(max(0.0, min(1.0,
                              0.55 * mode_term + 0.25 * tempo_term
                              + 0.20 * bright_term)), 3)


def _arousal(rms_db, onset_rate, tempo):
    """Approximate activation: loudness and event density, not a measurement."""
    loud = max(0.0, min(1.0, (rms_db + 30.0) / 26.0))
    density = max(0.0, min(1.0, onset_rate / 4.0))
    pace = max(0.0, min(1.0, (tempo - 60.0) / 100.0))
    return round(max(0.0, min(1.0, 0.45 * loud + 0.35 * density + 0.20 * pace)), 3)


def _danceability(beat_strength, tempo, percussive):
    """Approximate groove: steady strong beats at a danceable tempo."""
    if 90.0 <= tempo <= 130.0:
        tempo_term = 1.0
    else:
        # falls off away from the dance band, but never to zero
        dist = min(abs(tempo - 90.0), abs(tempo - 130.0))
        tempo_term = max(0.0, 1.0 - dist / 60.0)
    return round(max(0.0, min(1.0,
                              0.45 * beat_strength + 0.30 * tempo_term
                              + 0.25 * percussive)), 3)


def _acoustic_score(harmonic_ratio, dynamic_range_db, rolloff_hz):
    """
    Approximate 'is this an acoustic recording'.

    Acoustic material tends to be more harmonic, wider in dynamics, and darker
    in rolloff than programmed electronic material. This misreads a heavily
    compressed live recording and a clean synthesised string patch the same
    way; it is a heuristic, not a classifier.
    """
    harm = max(0.0, min(1.0, harmonic_ratio))
    dyn = max(0.0, min(1.0, dynamic_range_db / 14.0))
    dark = max(0.0, min(1.0, 1.0 - (rolloff_hz - 3000.0) / 7000.0))
    return round(max(0.0, min(1.0, 0.45 * harm + 0.30 * dyn + 0.25 * dark)), 3)


def _vocal_presence(harmonic, freqs, vocal_band):
    """
    Approximate 'is someone singing'.

    Lead vocals occupy a fairly narrow box — roughly 300–3400 Hz, harmonic,
    and not spectrally flat. Energy concentrated there in the *harmonic*
    component is weak evidence of a voice. An instrumental with a lead guitar
    in the same range will fool it, which is why it is discounted downstream.

    `freqs` must be the STFT bin frequencies for `harmonic` (librosa's
    fft_frequencies), not recomputed from the array shape — the first axis of
    an STFT is already the bin count, so rfftfreq would halve it.
    """
    lo, hi = vocal_band
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return 0.0

    mag = np.abs(harmonic)[mask]
    total = np.abs(harmonic).sum()
    if total <= 0:
        return 0.0
    band_share = float(mag.sum() / total)          # 0..1, typically 0.2..0.6

    # Centre the expectation: ~0.2 share is instrumental, ~0.55 is vocal-led.
    score = (band_share - 0.20) / 0.35
    return round(max(0.0, min(1.0, score)), 3)


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_features(path, verbose=False):
    """
    Analyse one audio file. Returns a dict keyed exactly like
    db._FEATURE_COLUMNS (the *_json columns hold plain Python lists here;
    db.save_features does the JSON encoding).

    Raises on unreadable files — the caller decides whether to skip.
    """
    librosa = _librosa()
    import pyloudnorm as pyln

    y, sr = librosa.load(str(path), sr=_SR, mono=True)
    if y.size == 0:
        raise ValueError(f"decoded to zero samples: {path}")

    duration = float(librosa.get_duration(y=y, sr=sr))

    # --- Family A: temporal & rhythmic ------------------------------------
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr,
                                           hop_length=_HOP)
    tempo = float(np.atleast_1d(tempo)[0])

    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr,
                                        hop_length=_HOP)
    onset_rate = float(len(onsets) / duration) if duration > 0 else 0.0

    # Beat strength: how far the onset envelope peaks above its own average.
    # A four-on-the-floor track sits high; a rubato ballad sits low.
    if onset_env.size:
        peak = float(np.percentile(onset_env, 90))
        mean = float(np.mean(onset_env)) + 1e-9
        beat_strength = max(0.0, min(1.0, (peak / mean - 1.0) / 2.5))
    else:
        beat_strength = 0.0

    # Rhythm complexity: how irregular the gaps between onsets are. A straight
    # dance beat has near-constant intervals (low); syncopated or free material
    # varies (high).
    if len(onsets) > 2:
        ioi = np.diff(librosa.frames_to_time(onsets, sr=sr, hop_length=_HOP))
        ioi = ioi[ioi > 0]
        if ioi.size > 1 and ioi.mean() > 0:
            rhythm_complexity = float(np.std(ioi) / ioi.mean())
        else:
            rhythm_complexity = 0.0
    else:
        rhythm_complexity = 0.0
    rhythm_complexity = max(0.0, min(1.0, rhythm_complexity))

    # --- Family C: spectral / timbre --------------------------------------
    S = np.abs(librosa.stft(y, hop_length=_HOP))
    freqs = librosa.fft_frequencies(sr=sr)

    centroid = librosa.feature.spectral_centroid(S=S, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y, hop_length=_HOP)

    spectral_centroid = float(np.mean(centroid))
    spectral_rolloff = float(np.mean(rolloff))
    spectral_bandwidth = float(np.mean(bandwidth))
    zero_crossing_rate = float(np.mean(zcr))

    # Band balance: share of total energy in low / mid / high. Stored as a
    # 3-vector and compared by cosine, so it captures *tilt*, not loudness.
    band_edges = [(0.0, 250.0), (250.0, 4000.0), (4000.0, float(sr / 2))]
    band_totals = []
    for lo, hi in band_edges:
        m = (freqs >= lo) & (freqs < hi)
        band_totals.append(float(S[m].sum()) if np.any(m) else 0.0)
    grand = sum(band_totals) or 1.0
    band_balance = [round(b / grand, 5) for b in band_totals]

    contrast = librosa.feature.spectral_contrast(S=S, sr=sr)
    spectral_contrast = [round(float(v), 5) for v in np.mean(contrast, axis=1)]

    mfcc_full = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=_N_MFCC, hop_length=_HOP)
    mfcc = [round(float(v), 5) for v in np.mean(mfcc_full, axis=1)]

    chroma_full = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=_HOP)
    chroma_mean = np.mean(chroma_full, axis=1)
    chroma = [round(float(v), 5) for v in chroma_mean]
    key_note, scale_mode, key_confidence = detect_key(chroma_mean)

    # --- Family B is above (chroma/key); Family E: instrumentation ---------
    # HPSS runs on its own, coarser STFT. The median-filter window that defines
    # "harmonic" vs "percussive" is kernel_size * hop_length samples, so
    # hop=1024/kernel=15 is the SAME 0.70s window as hop=512/kernel=31 — just
    # measured on half as many frames. Profiling this library: 47.5s -> 13.2s
    # per track with no change in the window being measured. The smoothing in
    # the median filter is what costs, and it scales with frame count.
    S_hp = np.abs(librosa.stft(y, hop_length=_HPSS_HOP))
    harmonic, percussive = librosa.effects.hpss(S_hp, kernel_size=_HPSS_KERNEL)
    h_energy = float(np.abs(harmonic).sum())
    p_energy = float(np.abs(percussive).sum())
    denom = h_energy + p_energy
    harmonic_ratio = (h_energy / denom) if denom > 0 else 0.5
    percussive_strength = (p_energy / denom) if denom > 0 else 0.5

    vocal_presence = _vocal_presence(harmonic, freqs, (300.0, 3400.0))

    # --- Family D: loudness & dynamics ------------------------------------
    # LUFS is the broadcast standard and is what the PRD's levelling stage
    # targets, so it is measured properly rather than approximated from RMS.
    try:
        meter = pyln.Meter(sr)
        loudness_lufs = float(meter.integrated_loudness(y))
        if not math.isfinite(loudness_lufs):
            loudness_lufs = None
    except Exception:
        loudness_lufs = None

    rms = librosa.feature.rms(y=y, hop_length=_HOP)[0]
    rms_energy = float(np.mean(rms))
    rms_db = 20.0 * math.log10(rms_energy + 1e-9)

    # Dynamic range: spread between the loud and quiet parts of the track,
    # in dB. Uses percentiles rather than max/min so one stray click or a
    # silent lead-in doesn't define it.
    if rms.size:
        loud_p = float(np.percentile(rms, 95)) + 1e-9
        quiet_p = float(np.percentile(rms, 10)) + 1e-9
        dynamic_range = float(20.0 * math.log10(loud_p / quiet_p))
    else:
        dynamic_range = 0.0

    peak = float(np.max(np.abs(y))) + 1e-9
    peak_db = 20.0 * math.log10(peak)
    peak_to_loudness = peak_db - loudness_lufs if loudness_lufs is not None else None

    # Energy envelope: the coarse shape of the track, for arc control. Eight
    # segments normalised to their own peak, so it describes build/drop, not
    # level.
    if rms.size >= _ENVELOPE_SEGMENTS:
        chunks = np.array_split(rms, _ENVELOPE_SEGMENTS)
        env = np.array([float(np.mean(c)) for c in chunks])
        top = env.max() or 1.0
        energy_envelope = [round(float(v / top), 4) for v in env]
    else:
        energy_envelope = []

    # --- Family G composites ----------------------------------------------
    energy_level = max(0.0, min(1.0, (rms_db + 30.0) / 26.0))
    valence_audio = _valence(scale_mode, tempo, spectral_centroid)
    arousal = _arousal(rms_db, onset_rate, tempo)
    danceability = _danceability(beat_strength, tempo, percussive_strength)

    feats = {
        "tempo_bpm": round(tempo, 2),
        "beat_strength": round(beat_strength, 4),
        "onset_rate": round(onset_rate, 3),
        "rhythm_complexity": round(rhythm_complexity, 4),

        "key_note": key_note,
        "scale_mode": scale_mode,
        "key_confidence": key_confidence,
        "chroma_json": chroma,

        "spectral_centroid": round(spectral_centroid, 2),
        "spectral_rolloff": round(spectral_rolloff, 2),
        "spectral_bandwidth": round(spectral_bandwidth, 2),
        "zero_crossing_rate": round(zero_crossing_rate, 5),
        "spectral_contrast_json": spectral_contrast,
        "band_balance_json": band_balance,
        "mfcc_json": mfcc,

        "loudness_lufs": round(loudness_lufs, 2) if loudness_lufs is not None else None,
        "rms_energy": round(rms_energy, 5),
        "dynamic_range": round(dynamic_range, 2),
        "peak_to_loudness": round(peak_to_loudness, 2) if peak_to_loudness is not None else None,
        "energy_envelope_json": energy_envelope,

        "percussive_strength": round(percussive_strength, 4),
        "harmonic_ratio": round(harmonic_ratio, 4),
        "acoustic_score": _acoustic_score(harmonic_ratio, dynamic_range,
                                          spectral_rolloff),
        "vocal_presence": vocal_presence,

        "energy_level": round(energy_level, 4),
        "valence_audio": valence_audio,
        "arousal": arousal,
        "danceability": danceability,
    }

    if verbose:
        print(f"    tempo={feats['tempo_bpm']:.1f} key={key_note} {scale_mode} "
              f"({key_confidence:.2f}) lufs={feats['loudness_lufs']} "
              f"energy={energy_level:.2f}")

    return feats


def extract_duration(path):
    """Duration in seconds without a full decode — used for the identity row."""
    librosa = _librosa()
    return float(librosa.get_duration(path=str(path)))
