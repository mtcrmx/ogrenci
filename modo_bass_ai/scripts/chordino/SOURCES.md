# Local Chordino runtime

Chordino and NNLS Chroma 1.1 are by Matthias Mauch and Chris Cannam at Queen Mary University of London. The original sources are compiled unmodified under GPL-2.0-or-later. The build uses Vamp Plugin SDK 2.10 from Chris Cannam and QMUL under its BSD-style terms and Boost 1.80 headers under Boost Software License 1.0. The runtime includes the Chordino and Vamp notices in `plugins`. [Chordino project](https://isophonics.net/nnls-chroma.html) · [Chordino sources](https://github.com/c4dm/nnls-chroma/tree/59f683ebb479c510b6b1a819ead3483778d72d4b) · [Vamp SDK sources](https://github.com/vamp-plugins/vamp-plugin-sdk/tree/67adfc2bf9486912a0fce5123cf54360ea2678bc) · [Boost license](https://www.boost.org/LICENSE_1_0.txt)

Sonic Annotator 1.7 runs the plugin in a separate Windows process. Its official binary distribution includes its notices, citations and license in `sonic-annotator-win64`. [Official binary and corresponding source](https://github.com/sonic-visualiser/sonic-annotator/releases/tag/sonic-annotator-1.7)

Rebuild locally with `python scripts/install_chordino.py` on Windows x64 with Visual Studio 2022 C++ and CMake available. Audio stays on the local computer.
