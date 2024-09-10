import subprocess
import sys
import os
import requests
import platform
from packaging import version


def get_windows_version():
    return platform.win32_ver()[1]


def download_file(url, filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def download_winget_prerequisites():
    temp_dir = os.environ.get('TEMP', os.path.join(os.environ.get('USERPROFILE'), 'AppData', 'Local', 'Temp'))

    version_vclibs = "14.00"
    file_vclibs = f"https://aka.ms/Microsoft.VCLibs.x64.{version_vclibs}.Desktop.appx"

    version_ui_xaml_minor = "2.8"
    version_ui_xaml_patch = "2.8.6"
    file_ui_xaml = f"https://github.com/microsoft/microsoft-ui-xaml/releases/download/v{version_ui_xaml_patch}/Microsoft.UI.Xaml.{version_ui_xaml_minor}.x64.appx"

    try:
        print("Microsoft.VCLibs 의존성 다운로드 중...")
        download_file(file_vclibs, os.path.join(temp_dir, "Microsoft.VCLibs.x64.Desktop.appx"))

        print("Microsoft.UI.Xaml 의존성 다운로드 중...")
        download_file(file_ui_xaml, os.path.join(temp_dir, "Microsoft.UI.Xaml.x64.appx"))

    except Exception as e:
        print(f"설치에 필요한 파일 다운로드 중 문제가 발생했습니다: {e}")
        return False

    return True


def download_winget_latest():
    temp_dir = os.environ.get('TEMP', os.path.join(os.environ.get('USERPROFILE'), 'AppData', 'Local', 'Temp'))

    try:
        response = requests.get("https://api.github.com/repos/microsoft/winget-cli/releases/latest")
        response.raise_for_status()
        release_data = response.json()

        latest_version = release_data['tag_name']
        print(f"최신 Winget 버전: {latest_version}")

        license_url = next(
            asset['browser_download_url'] for asset in release_data['assets'] if asset['name'].endswith('License1.xml'))
        msixbundle_url = next(
            asset['browser_download_url'] for asset in release_data['assets'] if asset['name'].endswith('.msixbundle'))

        print("Winget 라이센스 다운로드 중...")
        download_file(license_url, os.path.join(temp_dir, "License1.xml"))

        print("Winget 설치 프로그램 다운로드 중...")
        download_file(msixbundle_url, os.path.join(temp_dir, "Microsoft.DesktopAppInstaller.msixbundle"))

    except Exception as e:
        print(f"최신 Winget 릴리스를 가져오는 중 문제가 발생하였습니다: {e}")
        return False

    return True


def install_winget():
    print("Winget 설치 중...")

    win_version = get_windows_version()
    if version.parse(win_version) < version.parse("10.0.17763"):
        print("이 Windows 버전(1809 이전)에서는 Winget이 지원되지 않습니다.")
        return False

    if not download_winget_prerequisites() or not download_winget_latest():
        return False

    temp_dir = os.environ.get('TEMP', os.path.join(os.environ.get('USERPROFILE'), 'AppData', 'Local', 'Temp'))

    try:
        subprocess.run([
            "powershell",
            "-Command",
            f"Add-AppxProvisionedPackage -Online -PackagePath '{os.path.join(temp_dir, 'Microsoft.DesktopAppInstaller.msixbundle')}' " +
            f"-DependencyPackagePath '{os.path.join(temp_dir, 'Microsoft.VCLibs.x64.Desktop.appx')}', " +
            f"'{os.path.join(temp_dir, 'Microsoft.UI.Xaml.x64.appx')}' " +
            f"-LicensePath '{os.path.join(temp_dir, 'License1.xml')}'"
        ], check=True)

        source_url = "https://cdn.winget.microsoft.com/cache/source.msix"
        source_file = os.path.join(temp_dir, "winget_source.msix")
        print("Winget 소스 파일 다운로드 중...")
        download_file(source_url, source_file)

        subprocess.run([
            "powershell",
            "-Command",
            f"Add-AppxPackage -Path '{source_file}'"
        ], check=True)

        print("Winget이 성공적으로 설치되었습니다.")
        return True

    except Exception as e:
        print(f"Winget 설치 중 문제가 발생하였습니다: {e}")
        return False


def reload_environment():
    print("환경 변수 다시 로드 중...")

    env = os.environ.copy()

    process = subprocess.Popen(
        ['powershell', '-Command',
         '(Get-ChildItem -Path Env:).GetEnumerator() | ForEach-Object { $_.Name + "=" + $_.Value }'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )
    stdout, stderr = process.communicate()

    if stderr:
        print(f"환경 변수 다시 로드 중 오류 발생: {stderr}")
        return False

    for line in stdout.strip().split('\n'):
        name, value = line.split('=', 1)
        env[name] = value

    os.environ.update(env)

    print("환경 변수가 다시 로드되었습니다.")
    return True


def install_java(package_id):
    print(f"{package_id} 설치 중...")
    try:
        subprocess.run(
            ["winget", "install", "-e", "--id", package_id, "--accept-source-agreements", "--accept-package-agreements",
             "--silent", "--disable-interactivity"], check=True)
        print(f"{package_id}가 성공적으로 설치되었습니다.")
    except subprocess.CalledProcessError as e:
        print(f"{package_id} 설치 중 오류 발생: {e}")

def check_and_install_winget():
    winget_status = subprocess.run(["winget", "--version"], capture_output=True, text=True) == 0

    if not winget_status:
        if not install_winget():
            print("Winget 설치에 실패했습니다.")
            sys.exit(1)

        if not reload_environment():
            print("Winget 설치 후 환경 변수를 다시 로드하는데 실패했습니다. 이 파일을 다시 실행 시켜 주세요.")
            sys.exit(1)

        if subprocess.run(["winget", "--version"], capture_output=True, text=True) != 0:
            print("Winget 설치에 성공했지만 Winget 호출을 알 수 없는 이유로 실패했습니다. 이 파일을 다시 실행 시켜 주세요.")
            sys.exit(1)

    else:
        print("Winget이 이미 설치되어 있습니다.")


check_and_install_winget()

java_packages = [
    "Amazon.Corretto.8.JDK",
    "Amazon.Corretto.17.JDK",
    "Amazon.Corretto.21.JDK"
]

for package in java_packages:
    install_java(package)
