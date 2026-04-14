/**
 * Kaelis Style Audit Tool
 * 样式审计工具 - 扫描和分析内联样式
 */

const fs = require('fs');
const path = require('path');

const CONFIG = {
  pagesDir: './pages',
  outputDir: './audit-results',
  minStyleLength: 100  // 最小样式长度才记录
};

// 确保输出目录存在
if (!fs.existsSync(CONFIG.outputDir)) {
  fs.mkdirSync(CONFIG.outputDir, { recursive: true });
}

// 样式模式定义
const STYLE_PATTERNS = {
  reset: {
    name: '基础 Reset',
    pattern: /\*\s*\{\s*margin:\s*0;\s*padding:\s*0;\s*box-sizing:\s*border-box;?\s*\}/g,
    severity: 'high',
    recommendation: '移除 - 已由 variables.css 提供'
  },
  bodyBase: {
    name: 'Body 基础样式',
    pattern: /body\s*\{\s*font-family:[^}]+background:[^}]+color:[^}]+\}/gs,
    severity: 'high',
    recommendation: '移除 - 已由 variables.css 提供'
  },
  cardStyle: {
    name: '卡片样式',
    pattern: /\.[a-z-]*(?:card|panel|box)[^{]*\{[^}]*background:\s*rgba\(23,\s*23,\s*23[^}]*\}/gi,
    severity: 'medium',
    recommendation: '替换为 .card 类'
  },
  buttonPrimary: {
    name: '主按钮样式',
    pattern: /\.[a-z-]*(?:btn|button)[a-z-]*[^{]*\{[^}]*background:\s*linear-gradient\(135deg,\s*#8848F9[^}]*\}/gi,
    severity: 'medium',
    recommendation: '替换为 .btn-primary 类'
  },
  gridLayout: {
    name: '网格布局',
    pattern: /display:\s*grid;[^}]*grid-template-columns:/g,
    severity: 'low',
    recommendation: '考虑使用统一网格类'
  },
  flexLayout: {
    name: 'Flex 布局',
    pattern: /display:\s*flex;/g,
    severity: 'low',
    recommendation: '如常用可提取为工具类'
  },
  customColors: {
    name: '硬编码颜色',
    pattern: /color:\s*#(?!8848F9|3B82F6)[0-9a-fA-F]{6}/g,
    severity: 'medium',
    recommendation: '使用 CSS 变量'
  },
  mediaQueries: {
    name: '媒体查询',
    pattern: /@media\s*\([^)]+\)\s*\{/g,
    severity: 'low',
    recommendation: '确保断点与变量一致'
  }
};

// 分析单个文件
function analyzeFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const fileName = path.basename(filePath);
  
  const result = {
    file: fileName,
    totalStyleLength: 0,
    styleTags: 0,
    patterns: {},
    recommendations: [],
    extractableStyles: []
  };
  
  // 提取所有 style 标签
  const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  let match;
  
  while ((match = styleRegex.exec(content)) !== null) {
    result.styleTags++;
    const styleContent = match[1];
    result.totalStyleLength += styleContent.length;
    
    // 检测各种模式
    for (const [key, config] of Object.entries(STYLE_PATTERNS)) {
      const patternMatches = styleContent.match(config.pattern);
      if (patternMatches) {
        if (!result.patterns[key]) {
          result.patterns[key] = {
            count: 0,
            name: config.name,
            severity: config.severity,
            recommendation: config.recommendation,
            examples: []
          };
        }
        result.patterns[key].count += patternMatches.length;
        result.patterns[key].examples.push(...patternMatches.slice(0, 2));
      }
    }
    
    // 提取可迁移的样式（长度超过阈值的）
    if (styleContent.length > CONFIG.minStyleLength) {
      result.extractableStyles.push({
        length: styleContent.length,
        preview: styleContent.slice(0, 200) + '...'
      });
    }
  }
  
  // 生成建议
  for (const [key, pattern] of Object.entries(result.patterns)) {
    if (pattern.severity === 'high' || pattern.count > 2) {
      result.recommendations.push({
        priority: pattern.severity === 'high' ? 'P0' : pattern.count > 5 ? 'P1' : 'P2',
        issue: pattern.name,
        count: pattern.count,
        action: pattern.recommendation
      });
    }
  }
  
  return result;
}

// 分析所有页面
function auditAll() {
  console.log('\n🔍 Kaelis Style Audit Tool\n');
  
  const files = fs.readdirSync(CONFIG.pagesDir)
    .filter(f => f.endsWith('.html'))
    .map(f => path.join(CONFIG.pagesDir, f));
  
  const results = [];
  let totalStyleLength = 0;
  let totalStyleTags = 0;
  
  files.forEach((file, index) => {
    if (index % 20 === 0) {
      process.stdout.write(`\r  分析中... ${index + 1}/${files.length}`);
    }
    
    const result = analyzeFile(file);
    results.push(result);
    totalStyleLength += result.totalStyleLength;
    totalStyleTags += result.styleTags;
  });
  
  console.log(`\r  ✓ 分析完成: ${files.length} 个文件`);
  
  // 汇总统计
  const summary = {
    totalFiles: files.length,
    totalStyleLength,
    totalStyleTags,
    averageStyleLength: Math.round(totalStyleLength / files.length),
    highSeverityIssues: 0,
    mediumSeverityIssues: 0,
    lowSeverityIssues: 0,
    patternSummary: {}
  };
  
  results.forEach(r => {
    Object.values(r.patterns).forEach(p => {
      if (!summary.patternSummary[p.name]) {
        summary.patternSummary[p.name] = { count: 0, severity: p.severity };
      }
      summary.patternSummary[p.name].count += p.count;
      
      if (p.severity === 'high') summary.highSeverityIssues += p.count;
      else if (p.severity === 'medium') summary.mediumSeverityIssues += p.count;
      else summary.lowSeverityIssues += p.count;
    });
  });
  
  // 保存详细报告
  const reportPath = path.join(CONFIG.outputDir, 'style-audit-report.json');
  fs.writeFileSync(reportPath, JSON.stringify({ summary, results }, null, 2));
  
  // 生成可读报告
  generateReadableReport(summary, results);
  
  return { summary, results };
}

// 生成可读报告
function generateReadableReport(summary, results) {
  const report = [];
  
  report.push('╔══════════════════════════════════════════════════════════════╗');
  report.push('║                 Kaelis 样式审计报告                          ║');
  report.push('╚══════════════════════════════════════════════════════════════╝');
  report.push('');
  report.push('📊 总体统计:');
  report.push(`  分析文件数: ${summary.totalFiles}`);
  report.push(`  内联样式总长度: ${summary.totalStyleLength.toLocaleString()} 字符`);
  report.push(`  平均每个页面: ${summary.averageStyleLength} 字符`);
  report.push(`  样式标签总数: ${summary.totalStyleTags}`);
  report.push('');
  report.push('🚨 问题统计:');
  report.push(`  高优先级 (P0): ${summary.highSeverityIssues} 处`);
  report.push(`  中优先级 (P1): ${summary.mediumSeverityIssues} 处`);
  report.push(`  低优先级 (P2): ${summary.lowSeverityIssues} 处`);
  report.push('');
  report.push('📋 样式模式分布:');
  
  const sortedPatterns = Object.entries(summary.patternSummary)
    .sort((a, b) => b[1].count - a[1].count);
  
  sortedPatterns.forEach(([name, data]) => {
    const icon = data.severity === 'high' ? '🔴' : data.severity === 'medium' ? '🟡' : '🟢';
    report.push(`  ${icon} ${name}: ${data.count} 次`);
  });
  
  report.push('');
  report.push('🔧 需要优先处理的文件 (Top 10):');
  
  const topFiles = results
    .filter(r => r.totalStyleLength > 500)
    .sort((a, b) => b.totalStyleLength - a.totalStyleLength)
    .slice(0, 10);
  
  topFiles.forEach((r, i) => {
    report.push(`  ${i + 1}. ${r.file} (${r.totalStyleLength} 字符, ${r.styleTags} 个<style>)`);
  });
  
  report.push('');
  report.push('💡 迁移建议:');
  report.push('  1. 首先处理高优先级问题 (基础reset、body样式)');
  report.push('  2. 提取高频出现的卡片/按钮样式到组件库');
  report.push('  3. 统一媒体查询断点');
  report.push('  4. 将硬编码颜色替换为CSS变量');
  report.push('');
  
  const reportText = report.join('\n');
  fs.writeFileSync(path.join(CONFIG.outputDir, 'style-audit-report.txt'), reportText);
  
  console.log(reportText);
}

// 生成迁移任务列表
function generateMigrationTasks(results) {
  const tasks = [];
  
  results.forEach(r => {
    Object.values(r.patterns).forEach(p => {
      if (p.severity === 'high' || p.count > 3) {
        tasks.push({
          file: r.file,
          issue: p.name,
          severity: p.severity,
          count: p.count,
          action: p.recommendation,
          priority: p.severity === 'high' ? 1 : p.count > 5 ? 2 : 3
        });
      }
    });
  });
  
  // 按优先级排序
  tasks.sort((a, b) => a.priority - b.priority);
  
  fs.writeFileSync(
    path.join(CONFIG.outputDir, 'migration-tasks.json'),
    JSON.stringify(tasks, null, 2)
  );
  
  console.log(`\n📝 已生成迁移任务列表: ${tasks.length} 项`);
  return tasks;
}

// 主函数
function main() {
  const args = process.argv.slice(2);
  const command = args[0] || 'audit';
  
  switch (command) {
    case 'audit':
      const { summary, results } = auditAll();
      generateMigrationTasks(results);
      console.log(`\n✅ 审计报告已保存到: ${CONFIG.outputDir}/`);
      break;
    case 'tasks':
      const { results: r } = auditAll();
      generateMigrationTasks(r);
      break;
    default:
      console.log('Usage: node style-audit.js [audit|tasks]');
  }
}

main();
