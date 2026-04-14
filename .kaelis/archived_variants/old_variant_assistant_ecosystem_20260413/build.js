/**
 * Kaelis Template Build System
 * Handlebars 模板构建脚本
 */

const fs = require('fs');
const path = require('path');
const Handlebars = require('handlebars');

// 配置
const CONFIG = {
  templatesDir: './templates',
  outputDir: './pages',
  assetsPath: '../assets',
  basePath: ''
};

// 注册 partials
function registerPartials() {
  const partialsDir = path.join(CONFIG.templatesDir, 'partials');
  
  if (fs.existsSync(partialsDir)) {
    fs.readdirSync(partialsDir).forEach(file => {
      if (file.endsWith('.hbs')) {
        const name = file.replace('.hbs', '');
        const content = fs.readFileSync(path.join(partialsDir, file), 'utf8');
        Handlebars.registerPartial(name, content);
        console.log(`✓ Registered partial: ${name}`);
      }
    });
  }
}

// 编译布局模板
function compileLayouts() {
  const layouts = {};
  const layoutsDir = path.join(CONFIG.templatesDir, 'layouts');
  
  if (fs.existsSync(layoutsDir)) {
    fs.readdirSync(layoutsDir).forEach(file => {
      if (file.endsWith('.hbs')) {
        const name = file.replace('.hbs', '');
        const content = fs.readFileSync(path.join(layoutsDir, file), 'utf8');
        layouts[name] = Handlebars.compile(content);
        console.log(`✓ Compiled layout: ${name}`);
      }
    });
  }
  
  return layouts;
}

// 构建页面
function buildPage(pageName, layouts) {
  const pageConfigPath = path.join(CONFIG.templatesDir, 'pages', `${pageName}.json`);
  
  if (!fs.existsSync(pageConfigPath)) {
    console.error(`✗ Page config not found: ${pageName}`);
    return false;
  }
  
  // 读取页面配置
  const pageConfig = JSON.parse(fs.readFileSync(pageConfigPath, 'utf8'));
  
  // 添加全局配置
  const context = {
    ...pageConfig,
    assetsPath: CONFIG.assetsPath,
    basePath: CONFIG.basePath
  };
  
  // 确定布局
  const layoutName = pageConfig.layout || 'main';
  const layout = layouts[layoutName];
  
  if (!layout) {
    console.error(`✗ Layout not found: ${layoutName}`);
    return false;
  }
  
  // 渲染页面内容
  let pageContent = '';
  if (pageConfig.contentTemplate) {
    const contentTemplatePath = path.join(CONFIG.templatesDir, 'contents', `${pageConfig.contentTemplate}.hbs`);
    if (fs.existsSync(contentTemplatePath)) {
      const contentTemplate = Handlebars.compile(fs.readFileSync(contentTemplatePath, 'utf8'));
      pageContent = contentTemplate(context);
    }
  }
  
  // 合并内容到上下文
  context.content = pageContent;
  
  // 渲染完整页面
  const html = layout(context);
  
  // 输出文件
  const outputPath = path.join(CONFIG.outputDir, `${pageName}.html`);
  fs.writeFileSync(outputPath, html, 'utf8');
  
  console.log(`✓ Built page: ${pageName}.html`);
  return true;
}

// 构建所有页面
function buildAll() {
  console.log('\n🚀 Kaelis Template Build System\n');
  
  // 注册 partials
  registerPartials();
  
  // 编译布局
  const layouts = compileLayouts();
  
  // 确保输出目录存在
  if (!fs.existsSync(CONFIG.outputDir)) {
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });
  }
  
  // 构建所有页面
  const pagesDir = path.join(CONFIG.templatesDir, 'pages');
  let builtCount = 0;
  
  if (fs.existsSync(pagesDir)) {
    fs.readdirSync(pagesDir).forEach(file => {
      if (file.endsWith('.json')) {
        const pageName = file.replace('.json', '');
        if (buildPage(pageName, layouts)) {
          builtCount++;
        }
      }
    });
  }
  
  console.log(`\n✅ Build complete! ${builtCount} pages generated.`);
}

// 开发模式 - 监听文件变化
function watch() {
  console.log('\n👀 Watching for changes...\n');
  
  buildAll();
  
  fs.watch(CONFIG.templatesDir, { recursive: true }, (eventType, filename) => {
    if (filename && (filename.endsWith('.hbs') || filename.endsWith('.json'))) {
      console.log(`\n📝 Changed: ${filename}`);
      buildAll();
    }
  });
}

// 注册 Handlebars 辅助函数
Handlebars.registerHelper('eq', function(a, b) {
  return a === b;
});

Handlebars.registerHelper('ne', function(a, b) {
  return a !== b;
});

Handlebars.registerHelper('gt', function(a, b) {
  return a > b;
});

Handlebars.registerHelper('lt', function(a, b) {
  return a < b;
});

Handlebars.registerHelper('and', function(a, b) {
  return a && b;
});

Handlebars.registerHelper('or', function(a, b) {
  return a || b;
});

Handlebars.registerHelper('not', function(a) {
  return !a;
});

Handlebars.registerHelper('json', function(context) {
  return JSON.stringify(context);
});

Handlebars.registerHelper('formatDate', function(date, format) {
  // 简单日期格式化
  const d = new Date(date);
  return d.toLocaleDateString('zh-CN');
});

Handlebars.registerHelper('uppercase', function(str) {
  return str ? str.toUpperCase() : '';
});

Handlebars.registerHelper('lowercase', function(str) {
  return str ? str.toLowerCase() : '';
});

Handlebars.registerHelper('truncate', function(str, length) {
  if (!str || str.length <= length) return str;
  return str.substring(0, length) + '...';
});

// 主函数
function main() {
  const args = process.argv.slice(2);
  const command = args[0] || 'build';
  
  switch (command) {
    case 'build':
      buildAll();
      break;
    case 'watch':
      watch();
      break;
    default:
      console.log('Usage: node build.js [build|watch]');
  }
}

main();
