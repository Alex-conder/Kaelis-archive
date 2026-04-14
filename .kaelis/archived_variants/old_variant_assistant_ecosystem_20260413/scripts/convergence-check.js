/**
 * Kaelis Convergence Check Tool
 * 收敛性检测工具 - 全面评估项目一致性
 */

const fs = require('fs');
const path = require('path');

const CONFIG = {
  pagesDir: './pages',
  assetsDir: './assets',
  templatesDir: './templates',
  outputDir: './audit-results'
};

// 检测指标
const METRICS = {
  cssVariables: { name: 'CSS变量系统', weight: 15 },
  components: { name: '组件库', weight: 15 },
  navigation: { name: '统一导航', weight: 15 },
  jsLogic: { name: 'JS逻辑', weight: 15 },
  inlineStyles: { name: '内联样式', weight: 15 },
  hardcodedColors: { name: '硬编码颜色', weight: 15 },
  templates: { name: '模板系统', weight: 10 }
};

// 检测单个文件
function checkFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const fileName = path.basename(filePath);
  
  return {
    file: fileName,
    metrics: {
      // CSS变量引用
      hasVariables: content.includes('variables.css'),
      
      // 组件库引用
      hasComponents: content.includes('components.css'),
      
      // 统一导航
      hasNavComponent: content.includes('nav-component.js'),
      hasNavMain: content.includes('nav-main'),
      
      // JS逻辑
      hasMainJs: content.includes('main.js'),
      hasAutoConverge: content.includes('auto-converge'),
      
      // 内联样式
      inlineStyleLength: (content.match(/<style[^>]*>([\s\S]*?)<\/style>/gi) || [])
        .reduce((sum, match) => sum + match.length, 0),
      
      // 硬编码颜色
      hardcodedColors: {
        purple: (content.match(/#8848F9/gi) || []).length,
        blue: (content.match(/#3B82F6/gi) || []).length,
        other: (content.match(/#[0-9A-Fa-f]{6}/g) || [])
          .filter(c => !['#8848F9', '#3B82F6'].includes(c.toUpperCase())).length
      },
      
      // 模板系统
      isTemplate: content.includes('{{') && content.includes('}}')
    }
  };
}

// 计算得分
function calculateScore(results) {
  const total = results.length;
  
  const scores = {
    cssVariables: results.filter(r => r.metrics.hasVariables).length / total * 100,
    components: results.filter(r => r.metrics.hasComponents).length / total * 100,
    navigation: results.filter(r => r.metrics.hasNavComponent || r.metrics.hasNavMain).length / total * 100,
    jsLogic: results.filter(r => r.metrics.hasMainJs && r.metrics.hasAutoConverge).length / total * 100,
    inlineStyles: Math.max(0, 100 - (results.reduce((sum, r) => sum + r.metrics.inlineStyleLength, 0) / total / 100)),
    hardcodedColors: Math.max(0, 100 - (results.reduce((sum, r) => 
      sum + r.metrics.hardcodedColors.purple + r.metrics.hardcodedColors.blue, 0) / total)),
    templates: results.filter(r => r.metrics.isTemplate).length / total * 100
  };
  
  // 加权总分
  let totalScore = 0;
  let totalWeight = 0;
  
  for (const [key, metric] of Object.entries(METRICS)) {
    totalScore += scores[key] * metric.weight;
    totalWeight += metric.weight;
  }
  
  return {
    overall: Math.round(totalScore / totalWeight),
    details: scores
  };
}

// 生成问题列表
function generateIssues(results) {
  const issues = [];
  
  results.forEach(r => {
    // 缺少CSS变量
    if (!r.metrics.hasVariables) {
      issues.push({ file: r.file, type: 'P0', issue: '缺少CSS变量系统', action: '添加variables.css引用' });
    }
    
    // 缺少组件库
    if (!r.metrics.hasComponents) {
      issues.push({ file: r.file, type: 'P1', issue: '缺少组件库', action: '添加components.css引用' });
    }
    
    // 缺少导航
    if (!r.metrics.hasNavComponent && !r.metrics.hasNavMain) {
      issues.push({ file: r.file, type: 'P1', issue: '缺少统一导航', action: '添加nav-component.js' });
    }
    
    // 大量内联样式
    if (r.metrics.inlineStyleLength > 5000) {
      issues.push({ file: r.file, type: 'P2', issue: `内联样式过多 (${r.metrics.inlineStyleLength}字符)`, action: '提取到外部CSS' });
    }
    
    // 硬编码颜色
    const hardcodedCount = r.metrics.hardcodedColors.purple + r.metrics.hardcodedColors.blue;
    if (hardcodedCount > 10) {
      issues.push({ file: r.file, type: 'P2', issue: `硬编码颜色 (${hardcodedCount}处)`, action: '替换为CSS变量' });
    }
  });
  
  // 按优先级排序
  const priorityOrder = { 'P0': 0, 'P1': 1, 'P2': 2 };
  return issues.sort((a, b) => priorityOrder[a.type] - priorityOrder[b.type]);
}

// 生成整改建议
function generateRecommendations(scores, issues) {
  const recommendations = [];
  
  // 根据得分生成建议
  if (scores.details.cssVariables < 100) {
    recommendations.push({
      priority: 'P0',
      area: 'CSS变量系统',
      current: `${scores.details.cssVariables.toFixed(1)}%`,
      target: '100%',
      action: '为未引用的页面添加variables.css',
      effort: '低',
      impact: '高'
    });
  }
  
  if (scores.details.components < 90) {
    recommendations.push({
      priority: 'P1',
      area: '组件库',
      current: `${scores.details.components.toFixed(1)}%`,
      target: '90%+',
      action: '推广components.css使用',
      effort: '低',
      impact: '高'
    });
  }
  
  if (scores.details.inlineStyles < 80) {
    recommendations.push({
      priority: 'P1',
      area: '内联样式',
      current: `${scores.details.inlineStyles.toFixed(1)}%`,
      target: '80%+',
      action: '使用style-migrate.js批量迁移',
      effort: '中',
      impact: '中'
    });
  }
  
  if (scores.details.hardcodedColors < 90) {
    recommendations.push({
      priority: 'P2',
      area: '硬编码颜色',
      current: `${scores.details.hardcodedColors.toFixed(1)}%`,
      target: '90%+',
      action: '运行style-migrate.js apply',
      effort: '低',
      impact: '中'
    });
  }
  
  if (scores.details.templates < 50) {
    recommendations.push({
      priority: 'P2',
      area: '模板系统',
      current: `${scores.details.templates.toFixed(1)}%`,
      target: '50%+',
      action: '逐步迁移页面到Handlebars模板',
      effort: '高',
      impact: '高'
    });
  }
  
  return recommendations;
}

// 主函数
function main() {
  console.log('\n🔍 Kaelis Convergence Check Tool\n');
  
  const files = fs.readdirSync(CONFIG.pagesDir)
    .filter(f => f.endsWith('.html'))
    .map(f => path.join(CONFIG.pagesDir, f));
  
  console.log(`正在检测 ${files.length} 个页面...\n`);
  
  const results = files.map((file, i) => {
    if (i % 20 === 0) process.stdout.write(`\r  进度: ${i + 1}/${files.length}`);
    return checkFile(file);
  });
  
  console.log(`\r  ✓ 检测完成: ${files.length} 个文件\n`);
  
  // 计算得分
  const scores = calculateScore(results);
  
  // 生成问题列表
  const issues = generateIssues(results);
  
  // 生成整改建议
  const recommendations = generateRecommendations(scores, issues);
  
  // 输出报告
  printReport(scores, issues, recommendations);
  
  // 保存报告
  const report = { scores, issues, recommendations, timestamp: new Date().toISOString() };
  fs.writeFileSync(
    path.join(CONFIG.outputDir, 'convergence-report.json'),
    JSON.stringify(report, null, 2)
  );
}

// 打印报告
function printReport(scores, issues, recommendations) {
  console.log('╔══════════════════════════════════════════════════════════════╗');
  console.log('║              Kaelis 收敛性检测报告                           ║');
  console.log('╚══════════════════════════════════════════════════════════════╝');
  console.log('');
  
  // 总分
  const scoreColor = scores.overall >= 90 ? '🟢' : scores.overall >= 80 ? '🟡' : '🔴';
  console.log(`${scoreColor} 总体收敛评分: ${scores.overall}/100`);
  console.log('');
  
  // 各维度得分
  console.log('📊 各维度得分:');
  for (const [key, metric] of Object.entries(METRICS)) {
    const score = scores.details[key];
    const icon = score >= 90 ? '✅' : score >= 70 ? '⚠️' : '❌';
    const bar = '█'.repeat(Math.round(score / 5)) + '░'.repeat(20 - Math.round(score / 5));
    console.log(`  ${icon} ${metric.name.padEnd(12)} [${bar}] ${score.toFixed(1)}%`);
  }
  console.log('');
  
  // 问题统计
  const p0Count = issues.filter(i => i.type === 'P0').length;
  const p1Count = issues.filter(i => i.type === 'P1').length;
  const p2Count = issues.filter(i => i.type === 'P2').length;
  
  console.log('🚨 问题统计:');
  console.log(`  🔴 P0 (紧急): ${p0Count} 项`);
  console.log(`  🟡 P1 (高): ${p1Count} 项`);
  console.log(`  🟢 P2 (中): ${p2Count} 项`);
  console.log('');
  
  // Top问题
  console.log('📋 优先处理问题 (Top 10):');
  issues.slice(0, 10).forEach((issue, i) => {
    const icon = issue.type === 'P0' ? '🔴' : issue.type === 'P1' ? '🟡' : '🟢';
    console.log(`  ${i + 1}. ${icon} [${issue.type}] ${issue.file}`);
    console.log(`     问题: ${issue.issue}`);
    console.log(`     建议: ${issue.action}`);
  });
  console.log('');
  
  // 整改建议
  console.log('💡 整改建议:');
  recommendations.forEach((rec, i) => {
    const icon = rec.priority === 'P0' ? '🔴' : rec.priority === 'P1' ? '🟡' : '🟢';
    console.log(`  ${i + 1}. ${icon} [${rec.priority}] ${rec.area}`);
    console.log(`     当前: ${rec.current} → 目标: ${rec.target}`);
    console.log(`     行动: ${rec.action}`);
    console.log(`     工作量: ${rec.effort} | 影响: ${rec.impact}`);
  });
  console.log('');
  
  // 总结
  console.log('✅ 报告已保存到: audit-results/convergence-report.json');
  console.log('');
}

main();
