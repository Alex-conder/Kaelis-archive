/**
 * Kaelis Style Migration Tool
 * 样式迁移工具 - 自动提取和迁移高频内联样式
 */

const fs = require('fs');
const path = require('path');

const CONFIG = {
  pagesDir: './pages',
  stylesDir: './assets/styles',
  backupDir: './backup/pages',
  dryRun: false  // 设置为 true 进行模拟运行
};

// 迁移规则
const MIGRATION_RULES = [
  {
    name: '基础 Reset 清理',
    pattern: /\*\s*\{\s*margin:\s*0;\s*padding:\s*0;\s*box-sizing:\s*border-box;?\s*\}/g,
    action: 'remove',
    reason: '已由 variables.css 提供'
  },
  {
    name: 'Body 基础样式清理',
    pattern: /body\s*\{\s*font-family:\s*[^}]+;\s*background:\s*[^}]+;\s*color:\s*[^}]+;\s*min-height:\s*100vh;?\s*\}/gs,
    action: 'remove',
    reason: '已由 variables.css 提供'
  },
  {
    name: '卡片样式统一',
    pattern: /(\.[a-z-]*(?:card|panel|box)[^{]*)\{\s*background:\s*rgba\(23,\s*23,\s*23[^}]*border:\s*1px\s+solid\s+rgba\(255,\s*255,\s*255,\s*0\.1\)[^}]*border-radius:\s*16px[^}]*\}/gi,
    action: 'replace',
    replacement: '$1 { @extend .card; }',
    reason: '使用统一 .card 类'
  },
  {
    name: '主按钮样式统一',
    pattern: /(\.[a-z-]*(?:btn|button)[a-z-]*-primary[^{]*)\{\s*background:\s*linear-gradient\(135deg,\s*#8848F9[^}]*\}/gi,
    action: 'replace',
    replacement: '$1 { @extend .btn-primary; }',
    reason: '使用统一 .btn-primary 类'
  },
  {
    name: '硬编码紫色替换',
    pattern: /#8848F9/g,
    action: 'replace',
    replacement: 'var(--primary)',
    reason: '使用 CSS 变量'
  },
  {
    name: '硬编码蓝色替换',
    pattern: /#3B82F6/g,
    action: 'replace',
    replacement: 'var(--secondary)',
    reason: '使用 CSS 变量'
  }
];

// 创建备份
function createBackup(filePath) {
  if (CONFIG.dryRun) return;
  
  const backupPath = filePath.replace('./pages', CONFIG.backupDir);
  const backupDir = path.dirname(backupPath);
  
  if (!fs.existsSync(backupDir)) {
    fs.mkdirSync(backupDir, { recursive: true });
  }
  
  fs.copyFileSync(filePath, backupPath);
}

// 迁移单个文件
function migrateFile(filePath) {
  const fileName = path.basename(filePath);
  let content = fs.readFileSync(filePath, 'utf8');
  let modified = false;
  const changes = [];
  
  // 提取 style 标签内容
  const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  let newContent = content;
  
  MIGRATION_RULES.forEach(rule => {
    const matches = newContent.match(rule.pattern);
    if (matches) {
      changes.push({
        rule: rule.name,
        count: matches.length,
        action: rule.action,
        reason: rule.reason
      });
      
      if (rule.action === 'remove') {
        newContent = newContent.replace(rule.pattern, '');
      } else if (rule.action === 'replace') {
        newContent = newContent.replace(rule.pattern, rule.replacement);
      }
      
      modified = true;
    }
  });
  
  // 清理空的 style 标签
  newContent = newContent.replace(/<style[^>]*>\s*<\/style>/gi, '');
  
  // 清理多个连续空行
  newContent = newContent.replace(/\n{3,}/g, '\n\n');
  
  return {
    fileName,
    modified,
    changes,
    originalSize: content.length,
    newSize: newContent.length,
    savings: content.length - newContent.length,
    newContent
  };
}

// 批量迁移
function migrateAll() {
  console.log('\n🔧 Kaelis Style Migration Tool\n');
  console.log(`模式: ${CONFIG.dryRun ? '模拟运行 (dry-run)' : '实际迁移'}\n`);
  
  const files = fs.readdirSync(CONFIG.pagesDir)
    .filter(f => f.endsWith('.html'))
    .map(f => path.join(CONFIG.pagesDir, f));
  
  const results = [];
  let totalSavings = 0;
  let modifiedCount = 0;
  
  files.forEach((file, index) => {
    if (index % 20 === 0) {
      process.stdout.write(`\r  处理中... ${index + 1}/${files.length}`);
    }
    
    const result = migrateFile(file);
    
    if (result.modified) {
      modifiedCount++;
      totalSavings += result.savings;
      
      // 创建备份并写入
      if (!CONFIG.dryRun) {
        createBackup(file);
        fs.writeFileSync(file, result.newContent, 'utf8');
      }
    }
    
    results.push(result);
  });
  
  console.log(`\r  ✓ 处理完成: ${files.length} 个文件`);
  
  // 生成报告
  generateReport(results, totalSavings, modifiedCount);
  
  return { results, totalSavings, modifiedCount };
}

// 生成报告
function generateReport(results, totalSavings, modifiedCount) {
  const report = [];
  
  report.push('╔══════════════════════════════════════════════════════════════╗');
  report.push('║              Kaelis 样式迁移报告                             ║');
  report.push('╚══════════════════════════════════════════════════════════════╝');
  report.push('');
  report.push('📊 总体统计:');
  report.push(`  处理文件数: ${results.length}`);
  report.push(`  修改文件数: ${modifiedCount}`);
  report.push(`  节省字符数: ${totalSavings.toLocaleString()} (${(totalSavings / 1024).toFixed(1)} KB)`);
  report.push(`  平均节省: ${modifiedCount > 0 ? Math.round(totalSavings / modifiedCount) : 0} 字符/文件`);
  report.push('');
  
  // 统计各规则应用次数
  const ruleStats = {};
  results.forEach(r => {
    r.changes.forEach(c => {
      if (!ruleStats[c.rule]) {
        ruleStats[c.rule] = { count: 0, savings: 0 };
      }
      ruleStats[c.rule].count += c.count;
    });
  });
  
  report.push('🔧 迁移规则应用:');
  Object.entries(ruleStats)
    .sort((a, b) => b[1].count - a[1].count)
    .forEach(([rule, stats]) => {
      report.push(`  • ${rule}: ${stats.count} 次`);
    });
  
  report.push('');
  report.push('📁 修改最多的文件 (Top 10):');
  
  const topFiles = results
    .filter(r => r.savings > 0)
    .sort((a, b) => b.savings - a.savings)
    .slice(0, 10);
  
  topFiles.forEach((r, i) => {
    report.push(`  ${i + 1}. ${r.fileName} (-${r.savings} 字符)`);
  });
  
  report.push('');
  report.push('✅ 迁移完成!');
  if (CONFIG.dryRun) {
    report.push('💡 这是模拟运行，实际文件未被修改。');
    report.push('   使用 node style-migrate.js apply 执行实际迁移。');
  }
  report.push('');
  
  const reportText = report.join('\n');
  fs.writeFileSync('./audit-results/migration-report.txt', reportText);
  
  console.log(reportText);
}

// 主函数
function main() {
  const args = process.argv.slice(2);
  const command = args[0] || 'dry-run';
  
  switch (command) {
    case 'dry-run':
      CONFIG.dryRun = true;
      migrateAll();
      break;
    case 'apply':
      CONFIG.dryRun = false;
      console.log('⚠️  这将实际修改文件，已创建备份到 backup/ 目录\n');
      migrateAll();
      break;
    default:
      console.log('Usage: node style-migrate.js [dry-run|apply]');
      console.log('  dry-run  - 模拟运行，不修改文件');
      console.log('  apply    - 执行实际迁移');
  }
}

main();
