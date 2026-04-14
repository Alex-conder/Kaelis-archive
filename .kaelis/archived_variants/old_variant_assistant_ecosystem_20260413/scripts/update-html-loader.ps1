# Kaelis HTML 页面批量更新脚本
# 将所有页面的脚本引用更新为使用 kaelis-loader.js

$pagesDir = "..\pages"
$loaderScript = '<script src="../assets/js/kaelis-loader.js" data-modules="standard"></script>'

# 定义页面和对应的模块组合
$pageModules = @{
    "login.html" = "basic,auth"
    "register.html" = "basic,auth"
    "dashboard.html" = "dashboard"
    "chat.html" = "chat"
    "ai-assistant.html" = "chat"
    "plugins.html" = "standard"
    "plugin-store.html" = "standard"
    "settings.html" = "standard"
    "settings-new.html" = "standard"
    "profile.html" = "standard"
    "billing.html" = "standard,billing"
    "monitoring.html" = "dashboard"
    "alerts.html" = "dashboard,alerts"
    "performance-monitor.html" = "dashboard,performance"
    "api-integration.html" = "standard,plugins"
    "file-manager.html" = "standard,binary"
    "batch-operations.html" = "standard,batch"
    "data-transfer.html" = "standard,binary"
    "security.html" = "standard,error-handler"
    "security-center.html" = "standard,error-handler"
    "help.html" = "basic"
    "help-center.html" = "basic"
    "status.html" = "basic"
    "team.html" = "standard"
    "collaboration.html" = "standard"
    "notifications.html" = "standard"
    "notification-center.html" = "standard"
    "logs.html" = "standard"
    "activity-logs.html" = "standard"
    "audit.html" = "standard"
    "compliance.html" = "standard"
    "rbac.html" = "standard"
    "integrations.html" = "standard,plugins"
    "webhooks.html" = "standard"
    "webhook-management.html" = "standard"
    "oauth-manager.html" = "standard"
    "scheduled-jobs.html" = "standard,batch"
    "scheduler.html" = "standard,batch"
    "pipeline.html" = "standard,batch"
    "workflow-designer.html" = "standard"
    "knowledge.html" = "standard"
    "knowledge-rag.html" = "standard"
    "models.html" = "standard"
    "model-management.html" = "standard"
    "model-marketplace.html" = "standard"
    "paper-management.html" = "standard"
    "peer-review.html" = "standard"
    "research-data.html" = "standard"
    "research-resources.html" = "standard"
    "ligand-protein-docking.html" = "standard"
    "meropenem-docking.html" = "standard"
    "vancomycin-docking.html" = "standard"
    "combination-docking.html" = "standard"
    "docking-analysis.html" = "standard"
    "3d-visualization.html" = "standard"
    "data-visualization.html" = "standard"
    "advanced-charts.html" = "standard"
    "chart-components.html" = "standard"
    "data-management.html" = "standard"
    "data-quality.html" = "standard"
    "data-sync.html" = "standard"
    "data-lineage.html" = "standard"
    "data-monitor-dashboard.html" = "dashboard"
    "cost-analysis.html" = "standard,billing"
    "capacity.html" = "standard"
    "disaster-recovery.html" = "standard"
    "backup-restore.html" = "standard"
    "cluster.html" = "standard"
    "topology.html" = "standard"
    "service-mesh.html" = "standard"
    "global-search.html" = "standard"
    "ticket-system.html" = "standard"
    "testing.html" = "standard"
    "testing-center.html" = "standard"
    "experiment-design.html" = "standard"
    "experiment-tracking.html" = "standard"
    "abtest.html" = "standard"
    "feature-flags.html" = "standard"
    "profiler.html" = "standard,performance"
    "code-editor.html" = "standard"
    "prompt-engineering.html" = "standard"
    "voice.html" = "standard"
    "ai-automation.html" = "standard"
    "character-system.html" = "standard"
    "docs-generator.html" = "standard"
    "import-export.html" = "standard"
    "api-docs.html" = "standard"
    "api-management.html" = "standard"
    "api-monitor.html" = "dashboard"
    "api-performance.html" = "dashboard,performance"
    "api-sandbox.html" = "standard"
    "api-auto-discovery.html" = "standard"
    "encryption-audit.html" = "standard"
    "system-health.html" = "dashboard"
    "system-updates.html" = "standard"
}

# 获取所有HTML文件
$htmlFiles = Get-ChildItem -Path $pagesDir -Filter "*.html"

$updatedCount = 0
$skippedCount = 0

foreach ($file in $htmlFiles) {
    $content = Get-Content $file.FullName -Raw
    
    # 检查是否包含旧的脚本引用
    if ($content -match '<script src="\.\./assets/js/(main|nav-component|auto-converge)\.js"') {
        # 确定模块组合
        $modules = "standard"
        if ($pageModules.ContainsKey($file.Name)) {
            $modules = $pageModules[$file.Name]
        }
        
        # 构建新的加载器脚本
        $newLoader = "    <!-- Kaelis 统一加载器 -->`n    <script src=`"../assets/js/kaelis-loader.js`" data-modules=`"$modules`"></script>"
        
        # 替换旧的脚本引用
        $pattern = '(\s*)<script src="\.\./assets/js/(main|nav-component|auto-converge)[^"]*\.js"[^>]*></script>(\s*)'
        $replacement = "$newLoader`n"
        
        # 移除所有匹配的脚本标签
        $newContent = $content -replace $pattern, ""
        
        # 清理多余的空行
        $newContent = $newContent -replace "(`n\s*){3,}", "`n`n"
        
        # 在 </body> 前插入新的加载器
        $newContent = $newContent -replace "(</body>)", "$newLoader`n`n`$1"
        
        # 保存文件
        Set-Content -Path $file.FullName -Value $newContent -NoNewline
        
        Write-Host "✓ 已更新: $($file.Name) (模块: $modules)" -ForegroundColor Green
        $updatedCount++
    } else {
        Write-Host "  跳过: $($file.Name) (无需更新)" -ForegroundColor Gray
        $skippedCount++
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "更新完成!" -ForegroundColor Cyan
Write-Host "已更新: $updatedCount 个文件" -ForegroundColor Green
Write-Host "跳过: $skippedCount 个文件" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
