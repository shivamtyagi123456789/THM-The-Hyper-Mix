/**
 * True Hyper Mixing (THM) — Interactive Web Frontend
 * Implements Video Concepts 1-4 & 52-Dimension Vibe Preservation
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const audio = document.getElementById("audio-player");
  const vinyl = document.getElementById("vinyl");
  const tonearm = document.getElementById("tonearm");
  const vinylTitle = document.getElementById("vinyl-title");
  const btnPlay = document.getElementById("btn-play");
  const playIcon = document.getElementById("play-icon");
  const pauseIcon = document.getElementById("pause-icon");
  const btnSkip = document.getElementById("btn-skip");
  const btnPrev = document.getElementById("btn-prev");
  const seekContainer = document.getElementById("seek-container");
  const seekFill = document.getElementById("seek-fill");
  const timeCurrent = document.getElementById("time-current");
  const timeDuration = document.getElementById("time-duration");
  const volumeSlider = document.getElementById("volume-slider");
  const arcButtons = document.querySelectorAll(".arc-btn");
  const activeArcLabel = document.getElementById("active-arc-label");

  const nowPlayingTitle = document.getElementById("now-playing-title");
  const nowPlayingArtist = document.getElementById("now-playing-artist");
  const heroStatus = document.getElementById("hero-status");
  const trackVibeTags = document.getElementById("track-vibe-tags");
  const telEnergy = document.getElementById("tel-energy");
  const telEnergyVal = document.getElementById("tel-energy-val");
  const telAcoustic = document.getElementById("tel-acoustic");
  const telAcousticVal = document.getElementById("tel-acoustic-val");
  const telVocal = document.getElementById("tel-vocal");
  const telVocalVal = document.getElementById("tel-vocal-val");
  const telLufsVal = document.getElementById("tel-lufs-val");

  const vuL = document.getElementById("vu-l");
  const vuR = document.getElementById("vu-r");

  const transitionCard = document.getElementById("transition-card");
  const bridgeOutTitle = document.getElementById("bridge-out-title");
  const bridgeOutBpm = document.getElementById("bridge-out-bpm");
  const bridgeInTitle = document.getElementById("bridge-in-title");
  const bridgeInBpm = document.getElementById("bridge-in-bpm");
  const bridgeMatchVal = document.getElementById("bridge-match-val");

  const lyricsScroll = document.getElementById("lyrics-scroll");
  const lyricsContent = document.getElementById("lyrics-content");
  const lyricsScriptTag = document.getElementById("lyrics-script-tag");
  const lyricsSyncIndicator = document.getElementById("lyrics-sync-indicator");

  const postersCarousel = document.getElementById("posters-carousel");
  const queueList = document.getElementById("queue-list");
  const queueCount = document.getElementById("queue-count");
  const libraryList = document.getElementById("library-list");
  const librarySearch = document.getElementById("library-search");

  const whyModal = document.getElementById("why-modal");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const modalScore = document.getElementById("modal-score");
  const modalAnchorName = document.getElementById("modal-anchor-name");
  const modalCandidateName = document.getElementById("modal-candidate-name");
  const modalTiebreak = document.getElementById("modal-tiebreak");
  const modalContribs = document.getElementById("modal-contribs");

  // State
  let currentTrack = null;
  let upcomingQueue = [];
  let lyricsData = [];
  let activeLyricIndex = -1;
  let allLibraryTracks = [];
  let currentPalette = { primary: "#0ea5e9", secondary: "#f59e0b" };
  let audioContext = null;
  let analyser = null;
  let sourceNode = null;
  let freqData = null;

  // ------------------------------------------------------------------------
  // Audio-Reactive Background Canvas (Video Concept 4)
  // ------------------------------------------------------------------------
  const auraCanvas = document.getElementById("ambient-aura-canvas");
  const ctx = auraCanvas.getContext("2d");
  let canvasW, canvasH;

  function resizeCanvas() {
    canvasW = auraCanvas.width = window.innerWidth;
    canvasH = auraCanvas.height = window.innerHeight;
  }
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  let auraAngle = 0;
  function renderAura() {
    requestAnimationFrame(renderAura);

    ctx.clearRect(0, 0, canvasW, canvasH);

    // Calculate energy / frequency modulation
    let bassIntensity = 0.5;
    let midIntensity = 0.5;
    if (analyser && !audio.paused) {
      analyser.getByteFrequencyData(freqData);
      let bassSum = 0;
      for (let i = 0; i < 16; i++) bassSum += freqData[i];
      bassIntensity = bassSum / (16 * 255);

      let midSum = 0;
      for (let i = 16; i < 64; i++) midSum += freqData[i];
      midIntensity = midSum / (48 * 255);

      // Animate VU meters
      if (vuL && vuR) {
        vuL.style.height = `${Math.min(100, Math.max(8, bassIntensity * 130))}%`;
        vuR.style.height = `${Math.min(100, Math.max(8, midIntensity * 140))}%`;
      }
    } else {
      if (vuL && vuR) {
        vuL.style.height = "5%";
        vuR.style.height = "5%";
      }
    }

    auraAngle += 0.006 + bassIntensity * 0.015;

    // Draw fluid procedural reactive orbs
    const cx = canvasW * 0.45;
    const cy = canvasH * 0.45;
    const radius1 = Math.min(canvasW, canvasH) * (0.42 + bassIntensity * 0.15);
    const radius2 = Math.min(canvasW, canvasH) * (0.35 + midIntensity * 0.2);

    const x1 = cx + Math.cos(auraAngle) * 80;
    const y1 = cy + Math.sin(auraAngle) * 60;
    const x2 = cx - Math.cos(auraAngle * 0.8) * 100;
    const y2 = cy - Math.sin(auraAngle * 0.8) * 80;

    // Gradient 1: Primary Aura
    const grad1 = ctx.createRadialGradient(x1, y1, 10, x1, y1, radius1);
    grad1.addColorStop(0, currentPalette.primary);
    grad1.addColorStop(1, "transparent");

    // Gradient 2: Secondary Accent Aura
    const grad2 = ctx.createRadialGradient(x2, y2, 20, x2, y2, radius2);
    grad2.addColorStop(0, currentPalette.secondary);
    grad2.addColorStop(1, "transparent");

    ctx.globalCompositeOperation = "screen";
    ctx.fillStyle = grad1;
    ctx.fillRect(0, 0, canvasW, canvasH);

    ctx.fillStyle = grad2;
    ctx.fillRect(0, 0, canvasW, canvasH);
    ctx.globalCompositeOperation = "source-over";
  }
  renderAura();

  function initAudioContext() {
    if (!audioContext) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioContext();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 128;
      freqData = new Uint8Array(analyser.frequencyBinCount);
      sourceNode = audioContext.createMediaElementSource(audio);
      sourceNode.connect(analyser);
      analyser.connect(audioContext.destination);
    }
    if (audioContext.state === "suspended") {
      audioContext.resume();
    }
  }

  // ------------------------------------------------------------------------
  // Playback & Needle Mechanics
  // ------------------------------------------------------------------------
  function setDeckPlaying(isPlaying) {
    if (isPlaying) {
      vinyl.classList.add("spinning");
      tonearm.classList.add("engaged");
      playIcon.classList.add("hidden");
      pauseIcon.classList.remove("hidden");
      heroStatus.textContent = "Master Output Active • Preserving Vibe";
    } else {
      vinyl.classList.remove("spinning");
      tonearm.classList.remove("engaged");
      playIcon.classList.remove("hidden");
      pauseIcon.classList.add("hidden");
      heroStatus.textContent = "Playback Paused";
    }
  }

  async function playTrack(trackId) {
    initAudioContext();
    try {
      const res = await fetch("/api/queue/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_id: trackId, queue_depth: 8 })
      });
      const data = await res.json();
      if (data.current_track) {
        applyTrackData(data.current_track);
        renderQueue(data.queue);
        loadAndPlayAudio(data.current_track.track_id);
        fetchLyrics(data.current_track.track_id);
      }
    } catch (e) {
      console.error("Failed to init track playback:", e);
    }
  }

  function loadAndPlayAudio(trackId) {
    audio.src = `/api/stream/${trackId}`;
    audio.load();
    audio.play().then(() => {
      setDeckPlaying(true);
    }).catch(err => {
      console.warn("Autoplay notice:", err);
      setDeckPlaying(false);
    });
  }

  function applyTrackData(track) {
    currentTrack = track;
    nowPlayingTitle.textContent = track.title || "Unknown Title";
    nowPlayingArtist.textContent = track.artist || "Unknown Artist";
    vinylTitle.textContent = (track.title || "THM").substring(0, 14);

    // Update tags
    trackVibeTags.innerHTML = `
      <span class="vibe-chip theme-chip">${track.primary_theme || 'unclassified'}</span>
      <span class="vibe-chip tempo-chip">${Math.round(track.tempo_bpm || 0)} BPM</span>
      <span class="vibe-chip key-chip">${track.key_note ? track.key_note + ' ' + (track.scale_mode || '') : 'KEY N/A'}</span>
    `;

    // Update Telemetry
    const energyPct = Math.round((track.energy_level || 0) * 100);
    telEnergy.style.width = `${energyPct}%`;
    telEnergyVal.textContent = (track.energy_level || 0).toFixed(2);

    const acousticPct = Math.round((track.acoustic_score || 0) * 100);
    telAcoustic.style.width = `${acousticPct}%`;
    telAcousticVal.textContent = (track.acoustic_score || 0).toFixed(2);

    const vocalPct = Math.round((track.vocal_presence || 0) * 100);
    telVocal.style.width = `${vocalPct}%`;
    telVocalVal.textContent = (track.vocal_presence || 0).toFixed(2);

    telLufsVal.textContent = `${(track.loudness_lufs || -14).toFixed(1)} dB`;

    // Dynamic aura palette selection
    if (track.primary_theme === "romance") {
      currentPalette = { primary: "rgba(239, 68, 68, 0.45)", secondary: "rgba(244, 114, 182, 0.35)" };
    } else if (track.primary_theme === "aggression") {
      currentPalette = { primary: "rgba(220, 38, 38, 0.55)", secondary: "rgba(249, 115, 22, 0.4)" };
    } else if (track.primary_theme === "heartbreak") {
      currentPalette = { primary: "rgba(147, 51, 234, 0.5)", secondary: "rgba(59, 130, 246, 0.35)" };
    } else if (track.primary_theme === "celebration" || track.primary_theme === "party") {
      currentPalette = { primary: "rgba(234, 179, 8, 0.5)", secondary: "rgba(16, 185, 129, 0.4)" };
    } else {
      currentPalette = { primary: "rgba(14, 165, 233, 0.45)", secondary: "rgba(99, 102, 241, 0.35)" };
    }
  }

  // ------------------------------------------------------------------------
  // Synced Lyrics (Video Concept 3)
  // ------------------------------------------------------------------------
  async function fetchLyrics(trackId) {
    lyricsContent.innerHTML = `<div class="lyric-line placeholder">Loading lyrical profile...</div>`;
    lyricsData = [];
    activeLyricIndex = -1;

    try {
      const res = await fetch(`/api/lyrics/${trackId}`);
      const data = await res.json();
      if (data.has_lyrics && data.lines && data.lines.length > 0) {
        lyricsData = data.lines;
        lyricsScriptTag.textContent = currentTrack && currentTrack.language ? currentTrack.language.toUpperCase() : "SYNCED";
        lyricsSyncIndicator.textContent = data.is_timed ? "Precision Synced" : "Tempo Spaced";

        lyricsContent.innerHTML = "";
        lyricsData.forEach((line, idx) => {
          const div = document.createElement("div");
          div.className = "lyric-line";
          div.dataset.index = idx;
          div.dataset.timeMs = line.time_ms;
          div.textContent = line.text;
          div.addEventListener("click", () => {
            audio.currentTime = line.time_ms / 1000;
          });
          lyricsContent.appendChild(div);
        });
      } else {
        lyricsContent.innerHTML = `<div class="lyric-line placeholder">No lyric file found for this track. Audio feature matching remains active.</div>`;
        lyricsSyncIndicator.textContent = "Audio Mode";
      }
    } catch (e) {
      console.error("Lyrics fetch failed:", e);
      lyricsContent.innerHTML = `<div class="lyric-line placeholder">Lyrics unavailable</div>`;
    }
  }

  function updateLyricsSync() {
    if (!lyricsData.length) return;
    const currentMs = audio.currentTime * 1000;

    let matchIdx = -1;
    for (let i = 0; i < lyricsData.length; i++) {
      if (currentMs >= lyricsData[i].time_ms) {
        matchIdx = i;
      } else {
        break;
      }
    }

    if (matchIdx !== activeLyricIndex && matchIdx >= 0) {
      activeLyricIndex = matchIdx;
      const allLines = lyricsContent.querySelectorAll(".lyric-line");
      allLines.forEach((el, i) => {
        if (i === activeLyricIndex) {
          el.classList.add("active");
          // Smooth scroll active line to center
          const containerH = lyricsScroll.clientHeight;
          const lineTop = el.offsetTop;
          lyricsScroll.scrollTo({
            top: lineTop - containerH / 2 + 20,
            behavior: "smooth"
          });
        } else {
          el.classList.remove("active");
        }
      });
    }
  }

  audio.addEventListener("timeupdate", () => {
    updateLyricsSync();
    if (audio.duration) {
      const pct = (audio.currentTime / audio.duration) * 100;
      seekFill.style.width = `${pct}%`;
      timeCurrent.textContent = formatTime(audio.currentTime);
      timeDuration.textContent = formatTime(audio.duration);

      // Check if approaching transition (last 15 seconds)
      if (audio.duration - audio.currentTime <= 15 && upcomingQueue.length > 0) {
        showTransitionPreview(currentTrack, upcomingQueue[0]);
      } else {
        transitionCard.classList.add("hidden");
      }
    }
  });

  function formatTime(secs) {
    if (isNaN(secs)) return "0:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  // Seek timeline click
  seekContainer.addEventListener("click", (e) => {
    const rect = seekContainer.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    if (audio.duration) {
      audio.currentTime = pos * audio.duration;
    }
  });

  // ------------------------------------------------------------------------
  // Intelligent Transition Visualizer (Video Concept 2)
  // ------------------------------------------------------------------------
  function showTransitionPreview(outgoing, incoming) {
    if (!outgoing || !incoming) return;
    bridgeOutTitle.textContent = outgoing.title || "Anchor";
    bridgeOutBpm.textContent = `${Math.round(outgoing.tempo_bpm || 0)} BPM`;

    bridgeInTitle.textContent = incoming.title || "Next Song";
    bridgeInBpm.textContent = `${Math.round(incoming.tempo_bpm || 0)} BPM`;

    bridgeMatchVal.textContent = `${incoming.match_percentage || 95}%`;
    transitionCard.classList.remove("hidden");
  }

  // ------------------------------------------------------------------------
  // Queue & Track Navigation
  // ------------------------------------------------------------------------
  function renderQueue(queue) {
    upcomingQueue = queue || [];
    queueCount.textContent = `${upcomingQueue.length} In Buffer`;
    queueList.innerHTML = "";

    if (!upcomingQueue.length) {
      queueList.innerHTML = `<div class="queue-empty-state">No upcoming tracks in buffer.</div>`;
      return;
    }

    upcomingQueue.forEach((item, idx) => {
      const div = document.createElement("div");
      div.className = "queue-item";
      div.innerHTML = `
        <div class="queue-item-info">
          <span class="q-title">${item.title}</span>
          <span class="q-artist">${item.artist}</span>
          <div class="q-meta-badges">
            <span class="q-badge">${item.theme}</span>
            <span class="q-badge">${Math.round(item.tempo_bpm)} BPM</span>
          </div>
        </div>
        <div class="queue-item-actions">
          <span class="match-score-pill">${item.match_percentage}%</span>
          <button class="btn-why" data-track-id="${item.track_id}">Why?</button>
        </div>
      `;

      // Click to jump to this track
      div.querySelector(".queue-item-info").addEventListener("click", () => {
        playTrack(item.track_id);
      });

      // Click "Why?" explanation
      div.querySelector(".btn-why").addEventListener("click", (e) => {
        e.stopPropagation();
        openWhyModal(currentTrack ? currentTrack.track_id : null, item.track_id);
      });

      queueList.appendChild(div);
    });
  }

  async function nextTrack() {
    try {
      const res = await fetch("/api/queue/next", { method: "POST" });
      const data = await res.json();
      if (data.current_track) {
        applyTrackData(data.current_track);
        renderQueue(data.queue);
        loadAndPlayAudio(data.current_track.track_id);
        fetchLyrics(data.current_track.track_id);
      }
    } catch (e) {
      console.error("Next track failed:", e);
    }
  }

  async function skipTrack() {
    try {
      const res = await fetch("/api/queue/skip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_id: currentTrack ? currentTrack.track_id : null })
      });
      const data = await res.json();
      if (data.current_track) {
        applyTrackData(data.current_track);
        renderQueue(data.queue);
        loadAndPlayAudio(data.current_track.track_id);
        fetchLyrics(data.current_track.track_id);
      }
    } catch (e) {
      console.error("Skip track failed:", e);
    }
  }

  // Transport button events
  btnPlay.addEventListener("click", () => {
    initAudioContext();
    if (audio.paused) {
      if (!audio.src && allLibraryTracks.length) {
        playTrack(allLibraryTracks[0].track_id);
      } else {
        audio.play().then(() => setDeckPlaying(true));
      }
    } else {
      audio.pause();
      setDeckPlaying(false);
    }
  });

  btnSkip.addEventListener("click", skipTrack);
  btnPrev.addEventListener("click", () => {
    if (audio.currentTime > 4) {
      audio.currentTime = 0;
    } else {
      skipTrack();
    }
  });

  audio.addEventListener("ended", nextTrack);

  volumeSlider.addEventListener("input", (e) => {
    audio.volume = parseFloat(e.target.value);
  });

  // Arc control toggles
  arcButtons.forEach(btn => {
    btn.addEventListener("click", async () => {
      arcButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const mode = btn.dataset.arc;
      activeArcLabel.textContent = mode.toUpperCase().replace("_", " ");

      try {
        const res = await fetch("/api/queue/arc", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: mode })
        });
        const data = await res.json();
        renderQueue(data.queue);
      } catch (err) {
        console.error("Failed to update arc:", err);
      }
    });
  });

  // ------------------------------------------------------------------------
  // Official Raftaar Showcase (Replacing Fruits from can ad)
  // ------------------------------------------------------------------------
  async function loadPosters() {
    try {
      const res = await fetch("/api/posters");
      const data = await res.json();
      postersCarousel.innerHTML = "";

      (data.posters || []).forEach(poster => {
        const card = document.createElement("div");
        card.className = "poster-card";
        card.style.background = poster.gradient;
        card.style.setProperty("--card-glow", poster.accent_glow);

        card.innerHTML = `
          <div class="poster-header">
            <span class="poster-badge" style="color: ${poster.accent}">${poster.theme}</span>
            <span class="poster-album">${poster.album}</span>
          </div>
          <div class="poster-center-art">
            <div class="poster-symbol" style="border-color: ${poster.accent}">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="${poster.accent}" stroke-width="2">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
              </svg>
            </div>
            <h4 class="poster-title">${poster.title}</h4>
            <p class="poster-artists">${poster.artist}</p>
          </div>
          <div class="poster-footer">
            <div class="poster-metrics">
              <span>${poster.bpm} BPM</span>
              <span>${poster.key}</span>
            </div>
            <button class="btn-poster-play">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="6 4 18 12 6 20 6 4"/></svg>
              Smart Mix
            </button>
          </div>
        `;

        card.addEventListener("click", () => {
          if (poster.library_track_id) {
            playTrack(poster.library_track_id);
          } else {
            // Find closest vibe anchor in library
            findBestMatchForPoster(poster);
          }
        });

        postersCarousel.appendChild(card);
      });
    } catch (e) {
      console.error("Failed to load posters:", e);
    }
  }

  function findBestMatchForPoster(poster) {
    // Search library for tracks by artist or theme
    const themeMatch = allLibraryTracks.find(t => t.primary_theme === poster.theme);
    if (themeMatch) {
      playTrack(themeMatch.track_id);
    } else if (allLibraryTracks.length) {
      playTrack(allLibraryTracks[0].track_id);
    }
  }

  // ------------------------------------------------------------------------
  // Library Explorer
  // ------------------------------------------------------------------------
  async function loadLibrary() {
    try {
      const res = await fetch("/api/tracks");
      const data = await res.json();
      allLibraryTracks = data.tracks || [];
      document.getElementById("lib-count-badge").textContent = `${data.total} Tracks Analysed`;
      renderLibrary(allLibraryTracks);

      // Default anchor: play "High On You" or first track on load
      const defaultTrack = allLibraryTracks.find(t => t.title.toLowerCase().includes("high on you")) || allLibraryTracks[0];
      if (defaultTrack && !currentTrack) {
        // Prepare track view without autoplaying immediately
        applyTrackData(defaultTrack);
        fetchLyrics(defaultTrack.track_id);
        fetch(`/api/queue/init`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ track_id: defaultTrack.track_id, queue_depth: 8 })
        }).then(r => r.json()).then(d => renderQueue(d.queue));
      }
    } catch (e) {
      console.error("Failed to load library:", e);
    }
  }

  function renderLibrary(tracks) {
    libraryList.innerHTML = "";
    tracks.slice(0, 50).forEach(tr => {
      const row = document.createElement("div");
      row.className = "lib-item";
      row.innerHTML = `
        <div>
          <div class="lib-item-title">${tr.title}</div>
          <div class="lib-item-artist">${tr.artist}</div>
        </div>
        <div class="lib-item-tempo">${Math.round(tr.tempo_bpm)} BPM</div>
      `;
      row.addEventListener("click", () => {
        playTrack(tr.track_id);
      });
      libraryList.appendChild(row);
    });
  }

  librarySearch.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    const filtered = allLibraryTracks.filter(t => 
      t.title.toLowerCase().includes(q) || 
      t.artist.toLowerCase().includes(q) || 
      t.primary_theme.toLowerCase().includes(q)
    );
    renderLibrary(filtered);
  });

  // ------------------------------------------------------------------------
  // "Why This Song?" Modal
  // ------------------------------------------------------------------------
  async function openWhyModal(anchorId, candidateId) {
    if (!anchorId || !candidateId) return;
    try {
      const res = await fetch(`/api/explain/${anchorId}/${candidateId}`);
      const data = await res.json();
      if (data.error) return;

      modalScore.textContent = `${data.overall_score}%`;
      modalAnchorName.textContent = `${data.anchor_title} (${data.anchor_artist})`;
      modalCandidateName.textContent = `${data.candidate_title} (${data.candidate_artist})`;
      modalTiebreak.textContent = data.tiebreak || "Score decided without tie-break";

      modalContribs.innerHTML = "";
      (data.top_matching_dimensions || []).forEach(c => {
        const div = document.createElement("div");
        div.className = "contrib-row";
        div.innerHTML = `
          <div class="contrib-dim">
            ${c.dimension}
            <span class="provenance">[${c.provenance}]</span>
          </div>
          <div class="contrib-score">${c.similarity}% Match</div>
        `;
        modalContribs.appendChild(div);
      });

      whyModal.classList.remove("hidden");
    } catch (e) {
      console.error("Failed to fetch explanation:", e);
    }
  }

  btnCloseModal.addEventListener("click", () => {
    whyModal.classList.add("hidden");
  });

  whyModal.addEventListener("click", (e) => {
    if (e.target === whyModal) {
      whyModal.classList.add("hidden");
    }
  });

  // Initial Load
  loadPosters();
  loadLibrary();
});
