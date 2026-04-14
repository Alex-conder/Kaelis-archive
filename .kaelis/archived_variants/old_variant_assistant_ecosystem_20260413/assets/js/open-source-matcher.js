/**
 * Kaelis Open Source File Matcher
 * 开源文件匹配模块 - 匹配开源许可证、检测开源组件、合规性检查
 */

(function() {
    'use strict';

    // 开源许可证类型
    const LICENSE_TYPE = {
        MIT: 'MIT',
        APACHE_2: 'Apache-2.0',
        GPL_V3: 'GPL-3.0',
        GPL_V2: 'GPL-2.0',
        BSD_3: 'BSD-3-Clause',
        BSD_2: 'BSD-2-Clause',
        LGPL: 'LGPL',
        MPL: 'MPL',
        EPL: 'EPL',
        CC0: 'CC0-1.0',
        UNLICENSE: 'Unlicense',
        PROPRIETARY: 'Proprietary',
        UNKNOWN: 'Unknown'
    };

    // 许可证兼容性矩阵
    const LICENSE_COMPATIBILITY = {
        [LICENSE_TYPE.MIT]: {
            compatible: [LICENSE_TYPE.MIT, LICENSE_TYPE.APACHE_2, LICENSE_TYPE.BSD_2, LICENSE_TYPE.BSD_3, LICENSE_TYPE.CC0, LICENSE_TYPE.UNLICENSE],
            canInclude: [LICENSE_TYPE.MIT, LICENSE_TYPE.BSD_2, LICENSE_TYPE.BSD_3, LICENSE_TYPE.CC0, LICENSE_TYPE.UNLICENSE],
            copyleft: false
        },
        [LICENSE_TYPE.APACHE_2]: {
            compatible: [LICENSE_TYPE.MIT, LICENSE_TYPE.APACHE_2, LICENSE_TYPE.BSD_2, LICENSE_TYPE.BSD_3],
            canInclude: [LICENSE_TYPE.MIT, LICENSE_TYPE.APACHE_2, LICENSE_TYPE.BSD_2, LICENSE_TYPE.BSD_3, LICENSE_TYPE.CC0],
            copyleft: false
        },
        [LICENSE_TYPE.GPL_V3]: {
            compatible: [LICENSE_TYPE.GPL_V3, LICENSE_TYPE.GPL_V2, LICENSE_TYPE.LGPL, LICENSE_TYPE.CC0],
            canInclude: [LICENSE_TYPE.GPL_V3, LICENSE_TYPE.LGPL, LICENSE_TYPE.MIT, LICENSE_TYPE.APACHE_2, LICENSE_TYPE.BSD_2, LICENSE_TYPE.BSD_3],
            copyleft: true
        },
        [LICENSE_TYPE.BSD_3]: {
            compatible: [LICENSE_TYPE.MIT, LICENSE_TYPE.APACHE_2, LICENSE_TYPE.BSD_2, LICENSE_TYPE.BSD_3],
            canInclude: [LICENSE_TYPE.MIT, LICENSE_TYPE.BSD_2, LICENSE_TYPE.BSD_3, LICENSE_TYPE.CC0],
            copyleft: false
        }
    };

    // 许可证关键词映射
    const LICENSE_KEYWORDS = {
        [LICENSE_TYPE.MIT]: ['mit license', 'permission is hereby granted', 'mit'],
        [LICENSE_TYPE.APACHE_2]: ['apache license', 'version 2.0', 'apache-2'],
        [LICENSE_TYPE.GPL_V3]: ['gnu general public license', 'version 3', 'gpl v3', 'gpl-3'],
        [LICENSE_TYPE.GPL_V2]: ['gnu general public license', 'version 2', 'gpl v2', 'gpl-2'],
        [LICENSE_TYPE.BSD_3]: ['bsd 3-clause', 'redistribution and use in source and binary forms'],
        [LICENSE_TYPE.BSD_2]: ['bsd 2-clause', 'simplified bsd'],
        [LICENSE_TYPE.LGPL]: ['lesser general public license', 'lgpl'],
        [LICENSE_TYPE.MPL]: ['mozilla public license', 'mpl'],
        [LICENSE_TYPE.CC0]: ['cc0', 'creative commons zero', 'public domain dedication']
    };

    /**
     * 许可证检测器
     */
    class LicenseDetector {
        constructor() {
            this.knownLicenses = new Map();
            this.confidenceThreshold = 0.8;
        }

        // 从文本检测许可证
        detectFromText(text) {
            const lowerText = text.toLowerCase();
            const scores = {};

            for (const [license, keywords] of Object.entries(LICENSE_KEYWORDS)) {
                let matches = 0;
                for (const keyword of keywords) {
                    if (lowerText.includes(keyword.toLowerCase())) {
                        matches++;
                    }
                }
                scores[license] = matches / keywords.length;
            }

            // 找出最高分
            let bestMatch = LICENSE_TYPE.UNKNOWN;
            let bestScore = 0;

            for (const [license, score] of Object.entries(scores)) {
                if (score > bestScore && score >= this.confidenceThreshold) {
                    bestScore = score;
                    bestMatch = license;
                }
            }

            return {
                license: bestMatch,
                confidence: bestScore,
                scores: scores
            };
        }

        // 从文件检测许可证
        async detectFromFile(file) {
            try {
                const text = await file.text();
                return this.detectFromText(text);
            } catch (error) {
                console.error('[LicenseDetector] 文件读取失败:', error);
                return { license: LICENSE_TYPE.UNKNOWN, confidence: 0 };
            }
        }

        // 检测LICENSE文件
        async detectLicenseFile(files) {
            const licenseFiles = files.filter(f => 
                /^license/i.test(f.name) || 
                /^copying/i.test(f.name) ||
                /^licence/i.test(f.name)
            );

            if (licenseFiles.length === 0) {
                return { license: LICENSE_TYPE.UNKNOWN, confidence: 0 };
            }

            // 读取第一个LICENSE文件
            return await this.detectFromFile(licenseFiles[0]);
        }

        // 检测文件头注释
        async detectHeaderLicense(file, extensions = ['.js', '.ts', '.py', '.java']) {
            if (!extensions.some(ext => file.name.endsWith(ext))) {
                return null;
            }

            try {
                const text = await file.text();
                // 提取前30行
                const header = text.split('\n').slice(0, 30).join('\n');
                return this.detectFromText(header);
            } catch (error) {
                return null;
            }
        }
    }

    /**
     * 开源组件匹配器
     */
    class OpenSourceComponentMatcher {
        constructor() {
            this.componentDatabase = new Map();
            this.loadDefaultComponents();
        }

        // 加载默认组件数据库
        loadDefaultComponents() {
            // 常见的开源组件
            const components = [
                { name: 'lodash', license: LICENSE_TYPE.MIT, patterns: ['lodash', '_'] },
                { name: 'react', license: LICENSE_TYPE.MIT, patterns: ['react', 'react-dom'] },
                { name: 'vue', license: LICENSE_TYPE.MIT, patterns: ['vue', 'vuejs'] },
                { name: 'angular', license: LICENSE_TYPE.MIT, patterns: ['angular', '@angular'] },
                { name: 'jquery', license: LICENSE_TYPE.MIT, patterns: ['jquery', '$'] },
                { name: 'bootstrap', license: LICENSE_TYPE.MIT, patterns: ['bootstrap'] },
                { name: 'axios', license: LICENSE_TYPE.MIT, patterns: ['axios'] },
                { name: 'express', license: LICENSE_TYPE.MIT, patterns: ['express'] },
                { name: 'fastapi', license: LICENSE_TYPE.MIT, patterns: ['fastapi'] },
                { name: 'django', license: LICENSE_TYPE.BSD_3, patterns: ['django'] },
                { name: 'flask', license: LICENSE_TYPE.BSD_3, patterns: ['flask'] },
                { name: 'tensorflow', license: LICENSE_TYPE.APACHE_2, patterns: ['tensorflow', 'tf.'] },
                { name: 'pytorch', license: LICENSE_TYPE.BSD_3, patterns: ['torch', 'pytorch'] },
                { name: 'scikit-learn', license: LICENSE_TYPE.BSD_3, patterns: ['sklearn', 'scikit-learn'] },
                { name: 'pandas', license: LICENSE_TYPE.BSD_3, patterns: ['pandas', 'pd'] },
                { name: 'numpy', license: LICENSE_TYPE.BSD_3, patterns: ['numpy', 'np'] },
                { name: 'matplotlib', license: LICENSE_TYPE.PROPRIETARY, patterns: ['matplotlib', 'plt'] }
            ];

            for (const component of components) {
                this.componentDatabase.set(component.name, component);
            }
        }

        // 从package.json匹配
        matchFromPackageJson(packageJson) {
            const matches = [];
            const deps = {
                ...packageJson.dependencies,
                ...packageJson.devDependencies
            };

            for (const [name, version] of Object.entries(deps || {})) {
                const component = this.findComponent(name);
                if (component) {
                    matches.push({
                        name: component.name,
                        version: version,
                        license: component.license,
                        source: 'package.json'
                    });
                }
            }

            return matches;
        }

        // 从代码匹配
        matchFromCode(code, language = 'javascript') {
            const matches = [];
            const found = new Set();

            for (const [name, component] of this.componentDatabase) {
                for (const pattern of component.patterns) {
                    if (code.includes(pattern) && !found.has(name)) {
                        matches.push({
                            name: component.name,
                            license: component.license,
                            pattern: pattern,
                            confidence: 'medium'
                        });
                        found.add(name);
                        break;
                    }
                }
            }

            return matches;
        }

        // 查找组件
        findComponent(name) {
            // 精确匹配
            if (this.componentDatabase.has(name)) {
                return this.componentDatabase.get(name);
            }

            // 模糊匹配
            for (const [key, component] of this.componentDatabase) {
                if (name.toLowerCase().includes(key.toLowerCase()) ||
                    key.toLowerCase().includes(name.toLowerCase())) {
                    return component;
                }
            }

            return null;
        }

        // 添加自定义组件
        addComponent(component) {
            this.componentDatabase.set(component.name, component);
        }
    }

    /**
     * 许可证合规性检查器
     */
    class LicenseComplianceChecker {
        constructor() {
            this.detector = new LicenseDetector();
            this.matcher = new OpenSourceComponentMatcher();
        }

        // 检查项目合规性
        async checkProject(projectFiles, projectLicense) {
            const report = {
                projectLicense: projectLicense,
                detectedLicenses: [],
                components: [],
                violations: [],
                warnings: [],
                summary: {
                    totalFiles: projectFiles.length,
                    licenseFiles: 0,
                    incompatibleLicenses: 0
                }
            };

            // 1. 检测LICENSE文件
            const licenseDetection = await this.detector.detectLicenseFile(projectFiles);
            if (licenseDetection.license !== LICENSE_TYPE.UNKNOWN) {
                report.detectedLicenses.push({
                    source: 'LICENSE file',
                    license: licenseDetection.license,
                    confidence: licenseDetection.confidence
                });
            }

            // 2. 检测package.json
            const packageJsonFile = projectFiles.find(f => f.name === 'package.json');
            if (packageJsonFile) {
                try {
                    const content = await packageJsonFile.text();
                    const packageJson = JSON.parse(content);
                    
                    // 匹配组件
                    const components = this.matcher.matchFromPackageJson(packageJson);
                    report.components.push(...components);

                    // 检查许可证字段
                    if (packageJson.license) {
                        report.detectedLicenses.push({
                            source: 'package.json',
                            license: packageJson.license,
                            confidence: 1.0
                        });
                    }
                } catch (error) {
                    console.error('[ComplianceChecker] package.json解析失败:', error);
                }
            }

            // 3. 检查许可证兼容性
            for (const component of report.components) {
                const check = this.checkCompatibility(projectLicense, component.license);
                
                if (!check.compatible) {
                    report.violations.push({
                        type: 'incompatible_license',
                        component: component.name,
                        componentLicense: component.license,
                        projectLicense: projectLicense,
                        reason: check.reason
                    });
                    report.summary.incompatibleLicenses++;
                } else if (check.warning) {
                    report.warnings.push({
                        type: 'license_warning',
                        component: component.name,
                        message: check.warning
                    });
                }
            }

            return report;
        }

        // 检查许可证兼容性
        checkCompatibility(projectLicense, dependencyLicense) {
            const compatibility = LICENSE_COMPATIBILITY[projectLicense];
            
            if (!compatibility) {
                return { compatible: true, warning: '未知项目许可证，无法检查兼容性' };
            }

            if (compatibility.canInclude.includes(dependencyLicense)) {
                return { compatible: true };
            }

            // 检查Copyleft
            const depCompat = LICENSE_COMPATIBILITY[dependencyLicense];
            if (depCompat && depCompat.copyleft) {
                return {
                    compatible: false,
                    reason: `${dependencyLicense} 是Copyleft许可证，可能与 ${projectLicense} 不兼容`
                };
            }

            return {
                compatible: false,
                reason: `${dependencyLicense} 与 ${projectLicense} 不兼容`
            };
        }

        // 生成合规性报告
        generateReport(checkResult) {
            const lines = [
                '# 开源许可证合规性报告',
                '',
                `生成时间: ${new Date().toISOString()}`,
                `项目许可证: ${checkResult.projectLicense}`,
                '',
                '## 检测到的许可证',
                ...checkResult.detectedLicenses.map(l => `- ${l.license} (来源: ${l.source}, 置信度: ${(l.confidence * 100).toFixed(1)}%)`),
                '',
                '## 开源组件',
                ...checkResult.components.map(c => `- ${c.name}@${c.version || 'unknown'} (${c.license})`),
                '',
                '## 违规',
                checkResult.violations.length === 0 ? '无' : ...checkResult.violations.map(v => `- ${v.component}: ${v.reason}`),
                '',
                '## 警告',
                checkResult.warnings.length === 0 ? '无' : ...checkResult.warnings.map(w => `- ${w.component}: ${w.message}`)
            ];

            return lines.join('\n');
        }
    }

    /**
     * SBOM生成器 (Software Bill of Materials)
     */
    class SBOMGenerator {
        constructor() {
            this.matcher = new OpenSourceComponentMatcher();
        }

        // 生成SBOM
        async generateSBOM(projectFiles, options = {}) {
            const sbom = {
                specVersion: '1.4',
                serialNumber: `urn:uuid:${this.generateUUID()}`,
                version: 1,
                metadata: {
                    timestamp: new Date().toISOString(),
                    tools: [{ name: 'Kaelis SBOM Generator', version: '1.0.0' }],
                    component: {
                        name: options.projectName || 'Unknown',
                        version: options.projectVersion || '1.0.0'
                    }
                },
                components: []
            };

            // 解析package.json
            const packageJsonFile = projectFiles.find(f => f.name === 'package.json');
            if (packageJsonFile) {
                const content = await packageJsonFile.text();
                const packageJson = JSON.parse(content);
                
                const deps = {
                    ...packageJson.dependencies,
                    ...packageJson.devDependencies
                };

                for (const [name, version] of Object.entries(deps || {})) {
                    const component = this.matcher.findComponent(name);
                    
                    sbom.components.push({
                        type: 'library',
                        name: name,
                        version: version,
                        licenses: [{
                            license: {
                                id: component?.license || LICENSE_TYPE.UNKNOWN
                            }
                        }],
                        purl: `pkg:npm/${name}@${version}`
                    });
                }
            }

            return sbom;
        }

        // 导出为不同格式
        exportSBOM(sbom, format = 'json') {
            switch (format.toLowerCase()) {
                case 'json':
                    return JSON.stringify(sbom, null, 2);
                case 'xml':
                    return this.toXML(sbom);
                case 'csv':
                    return this.toCSV(sbom);
                default:
                    return JSON.stringify(sbom, null, 2);
            }
        }

        toXML(sbom) {
            // 简化的XML转换
            let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<bom>\n';
            for (const component of sbom.components) {
                xml += `  <component type="${component.type}">\n`;
                xml += `    <name>${component.name}</name>\n`;
                xml += `    <version>${component.version}</version>\n`;
                xml += `  </component>\n`;
            }
            xml += '</bom>';
            return xml;
        }

        toCSV(sbom) {
            const lines = ['Name,Version,License,PURL'];
            for (const component of sbom.components) {
                const license = component.licenses?.[0]?.license?.id || 'Unknown';
                lines.push(`${component.name},${component.version},${license},${component.purl || ''}`);
            }
            return lines.join('\n');
        }

        generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
    }

    // 导出
    window.OpenSourceMatcher = {
        LicenseDetector,
        OpenSourceComponentMatcher,
        LicenseComplianceChecker,
        SBOMGenerator,
        LICENSE_TYPE,
        LICENSE_COMPATIBILITY
    };

    console.log('[OpenSourceMatcher] 开源文件匹配模块已加载');
})();
