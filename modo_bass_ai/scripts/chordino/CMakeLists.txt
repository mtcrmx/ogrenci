cmake_minimum_required(VERSION 3.20)
project(chordino LANGUAGES C CXX)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
file(GLOB NNLS LIST_DIRECTORIES true "nnls/nnls-chroma-*")
file(GLOB SDK LIST_DIRECTORIES true "vamp/vamp-plugin-sdk-*")
add_library(nnls-chroma SHARED
  "${NNLS}/Chordino.cpp" "${NNLS}/NNLSBase.cpp" "${NNLS}/NNLSChroma.cpp" "${NNLS}/Tuning.cpp"
  "${NNLS}/chromamethods.cpp" "${NNLS}/plugins.cpp" "${NNLS}/viterbi.cpp" "${NNLS}/nnls.c"
  "${SDK}/src/vamp-sdk/PluginAdapter.cpp" "${SDK}/src/vamp-sdk/RealTime.cpp"
  "${SDK}/src/vamp-sdk/FFT.cpp")
target_include_directories(nnls-chroma PRIVATE "${SDK}" "${CMAKE_SOURCE_DIR}/boost/lib/native/include")
target_compile_features(nnls-chroma PRIVATE cxx_std_14)
target_compile_definitions(nnls-chroma PRIVATE _USE_MATH_DEFINES NOMINMAX _CRT_SECURE_NO_WARNINGS BOOST_ALL_NO_LIB)
target_link_options(nnls-chroma PRIVATE /EXPORT:vampGetPluginDescriptor)
