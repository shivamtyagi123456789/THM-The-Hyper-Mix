from setuptools import setup, find_packages

setup(
    name="thm",
    version="1.0.0",
    description="True Hyper Mixing (THM) - 52-Dimension Vibe Preservation Playback Engine",
    author="Antigravity Team",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "flask>=3.0.0",
        "numpy>=1.24.0",
        "scipy>=1.11.0",
        "scikit-learn>=1.3.0",
        "mutagen>=1.47.0",
        "pyloudnorm>=0.1.1",
        "librosa>=0.10.0",
    ],
    entry_points={
        "console_scripts": [
            "thm-analyze=thm.analyze_library:main",
            "thm-explain=thm.explain:main",
        ],
    },
)
