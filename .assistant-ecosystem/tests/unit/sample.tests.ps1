Describe "OpenClaw Assistant Core" {
    Context "Configuration Loading" {
        It "Should load ecosystem.json without errors" {
            $configPath = Join-Path $PSScriptRoot "..\..\config\ecosystem.json"
            $config = Get-Content $configPath -Raw | ConvertFrom-Json
            $config | Should -Not -BeNullOrEmpty
        }
    }
    
    Context "Script Syntax Validation" {
        It "All .ps1 files should pass syntax check" {
            $binPath = Join-Path $PSScriptRoot "..\..\bin"
            $scripts = Get-ChildItem -Path $binPath -Filter "*.ps1" -Recurse
            $failures = @()
            foreach ($script in $scripts) {
                $errors = $null
                [System.Management.Automation.PSParser]::Tokenize((Get-Content $script.FullName -Raw), [ref]$errors)
                if ($errors.Count -gt 0) {
                    $failures += "$($script.Name): $($errors.Count) errors"
                }
            }
            $failures.Count | Should -Be 0
        }
    }
}
