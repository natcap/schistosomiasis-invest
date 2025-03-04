$clPath = Get-ChildItem -Path "C:\Program Files\", "C:\Program Files (x86)\" -Recurse -ErrorAction SilentlyContinue -Filter "cl.exe" | Select-Object -First 1
if ($clPath) {
	Write-Host "Visual Studio (and potentially the C++ compiler) is installed."
} else {
	Write-Host "Visual Studio (and the C++ compiler) may not be installed."
        # install micromamba dependencies: https://github.com/mamba-org/mamba/issues/2928
	Invoke-WebRequest -URI "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile "$env:Temp\vc_redist.x64.exe"; Start-Process "$env:Temp\vc_redist.x64.exe" -ArgumentList "/quiet /norestart" -Wait; Remove-Item "$env:Temp\vc_redist.x64.exe"
}
