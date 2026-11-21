"""Build optional Chordino for Windows x64. Requires CMake and VS 2022 C++."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "nnls": (
        "https://codeload.github.com/c4dm/nnls-chroma/zip/59f683ebb479c510b6b1a819ead3483778d72d4b",
        "bf6a5b369f71659d2d93dd71e0887bf56428956ed7771582a2960f181c100151",
    ),
    "vamp": (
        "https://codeload.github.com/vamp-plugins/vamp-plugin-sdk/zip/67adfc2bf9486912a0fce5123cf54360ea2678bc",
        "4e417443b2081265dea5d2a1c69366c1ecfde9e1636b8f9213ce859e5791edac",
    ),
    "host": (
        "https://github.com/sonic-visualiser/sonic-annotator/releases/download/sonic-annotator-1.7/sonic-annotator-1.7-win64.zip",
        "c40717e029210cf1e1c97bc7dadea00cf4386327e67fdf9ca66027a91ea26693",
    ),
    "boost": (
        "https://api.nuget.org/v3-flatcontainer/boost/1.80.0/boost.1.80.0.nupkg",
        "cfcc3cdcafdf4a8a71a19da5f9271c11e0d979b22be96114506dd78a36a306c6",
    ),
}


def fetch(build, name):
    url, expected = PACKAGES[name]
    with urlopen(url, timeout=90) as response:
        data = response.read()
    if sha256(data).hexdigest() != expected:
        raise ValueError(f"Unexpected checksum for {name}")
    with ZipFile(BytesIO(data)) as archive:
        archive.extractall(build / name)


def install():
    if os.name != "nt":
        raise SystemExit("The bundled build recipe targets Windows x64.")
    home = ROOT / ".tools"
    home.mkdir(exist_ok=True)
    runtime = home / "chordino"
    if runtime.exists():
        print(f"Already installed at {runtime}")
        return
    with (
        tempfile.TemporaryDirectory(prefix="chordino-") as tmp,
        tempfile.TemporaryDirectory(dir=home) as stage,
    ):
        build = Path(tmp)
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(lambda name: fetch(build, name), PACKAGES))
        shutil.copy2(Path(__file__).parent / "chordino" / "CMakeLists.txt", build)
        subprocess.run(
            [
                "cmake",
                "-S",
                ".",
                "-B",
                "build",
                "-G",
                "Visual Studio 17 2022",
                "-A",
                "x64",
            ],
            cwd=build,
            check=True,
        )
        subprocess.run(
            ["cmake", "--build", "build", "--config", "Release", "--parallel", "4"],
            cwd=build,
            check=True,
        )
        folder = Path(stage) / "chordino"
        folder.mkdir()
        shutil.copytree(
            build / "host" / "sonic-annotator-win64", folder / "sonic-annotator-win64"
        )
        plugins = folder / "plugins"
        plugins.mkdir()
        nnls = next((build / "nnls").iterdir())
        sdk = next((build / "vamp").iterdir())
        for name in ("nnls-chroma.cat", "nnls-chroma.n3", "COPYING", "CITATION"):
            shutil.copy2(nnls / name, plugins / name)
        shutil.copy2(sdk / "COPYING", plugins / "COPYING-vamp-sdk.txt")
        shutil.copy2(Path(__file__).parent / "chordino" / "LICENSE-Boost-1.0.txt", plugins)
        shutil.copy2(build / "build/Release/nnls-chroma.dll", plugins)
        shutil.copy2(Path(__file__).parent / "chordino" / "SOURCES.md", folder)
        env = dict(os.environ, VAMP_PATH=str(plugins), VAMP_PATH_64=str(plugins))
        probe = subprocess.check_output(
            [str(folder / "sonic-annotator-win64/sonic-annotator.exe"), "-l"], env=env
        )
        if b"vamp:nnls-chroma:chordino:simplechord" not in probe:
            raise RuntimeError(
                "Chordino was built but its chord estimator could not be loaded"
            )
        folder.rename(runtime)
    print(f"Installed at {runtime}")


if __name__ == "__main__":
    install()
