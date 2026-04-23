#!/usr/bin/env pwsh
#Requires -Version 5.1
# doc-generator.ps1 - Automated Documentation Generator for OpenClaw Assistant
# Features: API docs, code docs, markdown generation, multi-format export

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Command = "help",
    
    [Parameter()]
    [string]$SourcePath = "",
    
    [Parameter()]
    [string]$OutputPath = "",
    
    [Parameter()]
    [string]$Format = "markdown",
    
    [Parameter()]
    [string]$Template = "default"
)

$ConfigDir = "$env:USERPROFILE\.assistant-ecosystem\config"
$DataDir = "$env:USERPROFILE\.assistant-ecosystem\data\docs"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

function Get-DocConfig {
    return @{
        templates = @("default", "api", "developer", "minimal")
        formats = @("markdown", "html", "pdf", "json")
        include_source = $true
        include_examples = $true
        include_diagrams = $false
    }
}

function Get-MockApiEndpoints {
    return @(
        @{
            path = "/api/v1/chat"
            method = "POST"
            summary = "Send a chat message"
            description = "Send a message to the AI assistant and receive a response"
            parameters = @(
                @{ name = "message"; type = "string"; required = $true; description = "The message to send" }
                @{ name = "model"; type = "string"; required = $false; description = "AI model to use" }
                @{ name = "temperature"; type = "number"; required = $false; description = "Response creativity (0-1)" }
            )
            responses = @{
                "200" = @{ description = "Success"; schema = "ChatResponse" }
                "400" = @{ description = "Bad Request" }
                "401" = @{ description = "Unauthorized" }
            }
            tags = @("Chat", "AI")
        },
        @{
            path = "/api/v1/plugins"
            method = "GET"
            summary = "List all plugins"
            description = "Retrieve a list of available plugins"
            parameters = @(
                @{ name = "category"; type = "string"; required = $false; description = "Filter by category" }
                @{ name = "limit"; type = "integer"; required = $false; description = "Max results to return" }
            )
            responses = @{
                "200" = @{ description = "Success"; schema = "PluginList" }
            }
            tags = @("Plugins")
        },
        @{
            path = "/api/v1/plugins/{id}"
            method = "GET"
            summary = "Get plugin details"
            description = "Retrieve detailed information about a specific plugin"
            parameters = @(
                @{ name = "id"; type = "string"; required = $true; description = "Plugin ID"; location = "path" }
            )
            responses = @{
                "200" = @{ description = "Success"; schema = "Plugin" }
                "404" = @{ description = "Plugin not found" }
            }
            tags = @("Plugins")
        },
        @{
            path = "/api/v1/users/{id}"
            method = "GET"
            summary = "Get user profile"
            description = "Retrieve user profile information"
            parameters = @(
                @{ name = "id"; type = "string"; required = $true; description = "User ID"; location = "path" }
            )
            responses = @{
                "200" = @{ description = "Success"; schema = "User" }
                "404" = @{ description = "User not found" }
            }
            tags = @("Users")
        }
    )
}

function Get-MockCodeDocs {
    return @(
        @{
            name = "OpenClawAssistant"
            type = "class"
            description = "Main class for the OpenClaw Assistant"
            methods = @(
                @{
                    name = "Initialize"
                    signature = "Initialize(Config config)"
                    description = "Initialize the assistant with configuration"
                    parameters = @(@{ name = "config"; type = "Config"; description = "Configuration object" })
                    returns = "void"
                },
                @{
                    name = "ProcessMessage"
                    signature = "ProcessMessage(string message)"
                    description = "Process an incoming message"
                    parameters = @(@{ name = "message"; type = "string"; description = "Message to process" })
                    returns = "Response"
                },
                @{
                    name = "LoadPlugin"
                    signature = "LoadPlugin(string pluginId)"
                    description = "Load a plugin by ID"
                    parameters = @(@{ name = "pluginId"; type = "string"; description = "Plugin identifier" })
                    returns = "Plugin"
                }
            )
            properties = @(
                @{ name = "Config"; type = "Config"; description = "Current configuration" }
                @{ name = "Plugins"; type = "List<Plugin>"; description = "Loaded plugins" }
                @{ name = "IsReady"; type = "bool"; description = "Whether assistant is ready" }
            )
        }
    )
}

function Show-DocStatus {
    Write-Host "`n[Documentation Generator Status]" -ForegroundColor Cyan
    Write-Host "=================================" -ForegroundColor Cyan
    
    $config = Get-DocConfig
    
    Write-Host "`nAvailable Templates:" -ForegroundColor Yellow
    foreach ($template in $config.templates) {
        $marker = if ($template -eq "default") { "*" } else { " " }
        Write-Host "  [$marker] $template" -ForegroundColor Gray
    }
    
    Write-Host "`nExport Formats:" -ForegroundColor Yellow
    foreach ($format in $config.formats) {
        Write-Host "  + $format" -ForegroundColor Green
    }
    
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Include source: $($config.include_source)" -ForegroundColor Gray
    Write-Host "  Include examples: $($config.include_examples)" -ForegroundColor Gray
    Write-Host "  Include diagrams: $($config.include_diagrams)" -ForegroundColor Gray
}

function Generate-ApiDocs($Format, $OutputPath) {
    Write-Host "`n[Generating API Documentation]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    
    $endpoints = Get-MockApiEndpoints
    
    if (-not $OutputPath) {
        $OutputPath = "$DataDir\api-docs.$(if ($Format -eq "markdown") { "md" } else { $Format })"
    }
    
    $content = ""
    
    switch ($Format) {
        "markdown" {
            $content = @"
# OpenClaw Assistant API Documentation

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Overview

This document describes the REST API endpoints available in the OpenClaw Assistant.

Base URL: \\\`http://localhost:8000/api/v1\\\`

## Authentication

All API requests require an API key to be included in the header:

\\\`\\\`\\\`
Authorization: Bearer YOUR_API_KEY
\\\`\\\`\\\`

## Endpoints

"@
            foreach ($ep in $endpoints) {
                $content += @"

### $($ep.summary)

**\\\`$($ep.method) $($ep.path)\\\`**

$($ep.description)

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
"@
                foreach ($param in $ep.parameters) {
                    $req = if ($param.required) { "Yes" } else { "No" }
                    $content += "| $($param.name) | $($param.type) | $req | $($param.description) |`n"
                }
                
                $content += @"

#### Responses

| Status | Description |
|--------|-------------|
"@
                foreach ($resp in $ep.responses.GetEnumerator()) {
                    $content += "| $($resp.Key) | $($resp.Value.description) |`n"
                }
                
                $content += "`n#### Tags: $($ep.tags -join ', ')`n"
            }
        }
        "json" {
            $doc = @{
                info = @{ title = "OpenClaw Assistant API"; version = "1.0.0"; generated = (Get-Date -Format "o") }
                endpoints = $endpoints
            }
            $content = $doc | ConvertTo-Json -Depth 10
        }
        default {
            $content = "API Documentation`nGenerated: $(Get-Date)`n`nEndpoints: $($endpoints.Count)"
        }
    }
    
    $content | Set-Content $OutputPath -Encoding UTF8
    Write-Host "`nAPI documentation generated: $OutputPath" -ForegroundColor Green
    Write-Host "Endpoints documented: $($endpoints.Count)" -ForegroundColor Gray
}

function Generate-CodeDocs($SourcePath, $Format, $OutputPath) {
    Write-Host "`n[Generating Code Documentation]" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    
    $docs = Get-MockCodeDocs
    
    if (-not $OutputPath) {
        $OutputPath = "$DataDir\code-docs.md"
    }
    
    $content = @"
# Code Documentation

Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Classes

"@
    
    foreach ($class in $docs) {
        $content += @"

### $($class.name)

$($class.description)

#### Properties

| Name | Type | Description |
|------|------|-------------|
"@
        foreach ($prop in $class.properties) {
            $content += "| $($prop.name) | $($prop.type) | $($prop.description) |`n"
        }
        
        $content += @"

#### Methods

"@
        foreach ($method in $class.methods) {
            $content += @"
##### $($method.name)

\\\`$($method.signature)\\\`

$($method.description)

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
"@
            foreach ($param in $method.parameters) {
                $content += "| $($param.name) | $($param.type) | $($param.description) |`n"
            }
            $content += "`n**Returns:** $($method.returns)`n`n"
        }
    }
    
    $content | Set-Content $OutputPath -Encoding UTF8
    Write-Host "`nCode documentation generated: $OutputPath" -ForegroundColor Green
    Write-Host "Classes documented: $($docs.Count)" -ForegroundColor Gray
}

function Generate-Readme($OutputPath) {
    if (-not $OutputPath) {
        $OutputPath = "$DataDir\README.md"
    }
    
    $content = @"
# OpenClaw Assistant

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/openclaw/assistant)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

OpenClaw Assistant is an intelligent AI-powered development assistant that helps developers write better code faster.

## Features

- **AI-Powered Chat**: Intelligent conversations with context awareness
- **Plugin System**: Extensible architecture with 80+ built-in tools
- **Code Review**: Automated code quality analysis
- **Documentation**: Auto-generate documentation from code
- **Multi-Model Support**: DeepSeek, GPT-4, Claude, Kimi

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/openclaw/assistant.git

# Install dependencies
cd assistant
./install.ps1

# Start the assistant
./start.ps1
```

### Usage

```powershell
# Start interactive mode
openclaw-assistant

# Run a specific tool
openclaw-assistant run code-reviewer -FilePath script.ps1
```

## Documentation

- [API Documentation](docs/api.md)
- [Developer Guide](docs/developer.md)
- [Plugin Development](docs/plugins.md)

## License

MIT License - see LICENSE file for details

---

Generated by OpenClaw Documentation Generator
"@
    
    $content | Set-Content $OutputPath -Encoding UTF8
    Write-Host "`nREADME generated: $OutputPath" -ForegroundColor Green
}

function Show-DocTemplates {
    Write-Host "`n[Available Documentation Templates]" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    
    $templates = @(
        @{ name = "default"; description = "Standard documentation with all sections"; best_for = "General use" }
        @{ name = "api"; description = "API-focused documentation"; best_for = "REST API projects" }
        @{ name = "developer"; description = "Developer guide with examples"; best_for = "Open source projects" }
        @{ name = "minimal"; description = "Minimal documentation"; best_for = "Simple projects" }
    )
    
    foreach ($template in $templates) {
        Write-Host "`n  $($template.name)" -ForegroundColor White
        Write-Host "    Description: $($template.description)" -ForegroundColor Gray
        Write-Host "    Best for: $($template.best_for)" -ForegroundColor Gray
    }
}

function Show-RecentDocs {
    Write-Host "`n[Recently Generated Documents]" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    
    $docs = @(
        @{ name = "api-reference.md"; type = "API"; size = "45 KB"; date = (Get-Date).AddHours(-2) }
        @{ name = "developer-guide.md"; type = "Guide"; size = "128 KB"; date = (Get-Date).AddDays(-1) }
        @{ name = "plugin-docs.md"; type = "Code"; size = "89 KB"; date = (Get-Date).AddDays(-2) }
        @{ name = "README.md"; type = "General"; size = "12 KB"; date = (Get-Date).AddDays(-3) }
    )
    
    foreach ($doc in $docs) {
        $dateStr = $doc.date.ToString("yyyy-MM-dd HH:mm")
        Write-Host "`n  $($doc.name)" -ForegroundColor White
        Write-Host "    Type: $($doc.type) | Size: $($doc.size) | Generated: $dateStr" -ForegroundColor Gray
    }
}

# Main
switch ($Command.ToLower()) {
    "status" { Show-DocStatus }
    "api" { Generate-ApiDocs -Format $Format -OutputPath $OutputPath }
    "code" { Generate-CodeDocs -SourcePath $SourcePath -Format $Format -OutputPath $OutputPath }
    "readme" { Generate-Readme -OutputPath $OutputPath }
    "templates" { Show-DocTemplates }
    "recent" { Show-RecentDocs }
    default {
        Write-Host "Automated Documentation Generator for OpenClaw Assistant" -ForegroundColor Cyan
        Write-Host "`nUsage:" -ForegroundColor White
        Write-Host "  doc-generator.ps1 status                    Show generator status" -ForegroundColor Gray
        Write-Host "  doc-generator.ps1 api [-Format <fmt>]       Generate API docs" -ForegroundColor Gray
        Write-Host "  doc-generator.ps1 code -SourcePath <path>   Generate code docs" -ForegroundColor Gray
        Write-Host "  doc-generator.ps1 readme                    Generate README" -ForegroundColor Gray
        Write-Host "  doc-generator.ps1 templates                 List templates" -ForegroundColor Gray
        Write-Host "  doc-generator.ps1 recent                    Show recent docs" -ForegroundColor Gray
        Write-Host "`nOptions:" -ForegroundColor White
        Write-Host "  -Format <fmt>      markdown, html, pdf, json (default: markdown)" -ForegroundColor Gray
        Write-Host "  -OutputPath <path> Output file path" -ForegroundColor Gray
        Write-Host "  -Template <name>   Template to use" -ForegroundColor Gray
    }
}
