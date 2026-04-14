/**
 * Kaelis Open Source Matcher Enhanced
 * 增强版开源文件匹配模块 - 参考SPDX、FOSSology、ScanCode最佳实践
 * 增加：SPDX标准支持、模糊匹配算法、多源验证、依赖树分析
 */

(function() {
    'use strict';

    // SPDX许可证标识符（参考https://spdx.org/licenses/）
    const SPDX_LICENSES = {
        'MIT': { name: 'MIT License', osiApproved: true, deprecated: false },
        'Apache-2.0': { name: 'Apache License 2.0', osiApproved: true, deprecated: false },
        'GPL-3.0-only': { name: 'GNU General Public License v3.0 only', osiApproved: true, deprecated: false },
        'GPL-3.0-or-later': { name: 'GNU General Public License v3.0 or later', osiApproved: true, deprecated: false },
        'GPL-2.0-only': { name: 'GNU General Public License v2.0 only', osiApproved: true, deprecated: false },
        'GPL-2.0-or-later': { name: 'GNU General Public License v2.0 or later', osiApproved: true, deprecated: false },
        'LGPL-3.0-only': { name: 'GNU Lesser General Public License v3.0 only', osiApproved: true, deprecated: false },
        'LGPL-2.1-only': { name: 'GNU Lesser General Public License v2.1 only', osiApproved: true, deprecated: false },
        'BSD-3-Clause': { name: 'BSD 3-Clause "New" or "Revised" License', osiApproved: true, deprecated: false },
        'BSD-2-Clause': { name: 'BSD 2-Clause "Simplified" License', osiApproved: true, deprecated: false },
        'MPL-2.0': { name: 'Mozilla Public License 2.0', osiApproved: true, deprecated: false },
        'EPL-2.0': { name: 'Eclipse Public License 2.0', osiApproved: true, deprecated: false },
        'CC0-1.0': { name: 'Creative Commons Zero v1.0 Universal', osiApproved: false, deprecated: false },
        'Unlicense': { name: 'The Unlicense', osiApproved: true, deprecated: false },
        'ISC': { name: 'ISC License', osiApproved: true, deprecated: false },
        'JSON': { name: 'JSON License', osiApproved: false, deprecated: false },
        'Proprietary': { name: 'Proprietary License', osiApproved: false, deprecated: false },
        'NOASSERTION': { name: 'NOASSERTION', osiApproved: false, deprecated: false }
    };

    // 许可证兼容性矩阵（基于FSF和OSI指南）
    const LICENSE_COMPATIBILITY_MATRIX = {
        'MIT': {
            canCombineWith: ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', 'CC0-1.0', 'Unlicense'],
            canRelicenseTo: ['MIT', 'Apache-2.0', 'GPL-3.0-only', 'GPL-3.0-or-later', 'Proprietary'],
            copyleft: false,
            strongCopyleft: false
        },
        'Apache-2.0': {
            canCombineWith: ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'GPL-3.0-only', 'GPL-3.0-or-later'],
            canRelicenseTo: ['Apache-2.0', 'GPL-3.0-only', 'GPL-3.0-or-later', 'Proprietary'],
            copyleft: false,
            strongCopyleft: false,
            patentGrant: true
        },
        'GPL-3.0-only': {
            canCombineWith: ['GPL-3.0-only', 'GPL-3.0-or-later', 'LGPL-3.0-only', 'LGPL-2.1-only', 'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause'],
            canRelicenseTo: ['GPL-3.0-only', 'GPL-3.0-or-later'],
            copyleft: true,
            strongCopyleft: true
        },
        'GPL-3.0-or-later': {
            canCombineWith: ['GPL-3.0-only', 'GPL-3.0-or-later', 'LGPL-3.0-only', 'LGPL-2.1-only', 'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause'],
            canRelicenseTo: ['GPL-3.0-or-later'],
            copyleft: true,
            strongCopyleft: true
        },
        'BSD-3-Clause': {
            canCombineWith: ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'CC0-1.0', 'Unlicense'],
            canRelicenseTo: ['MIT', 'Apache-2.0', 'BSD-3-Clause', 'GPL-3.0-only', 'GPL-3.0-or-later', 'Proprietary'],
            copyleft: false,
            strongCopyleft: false
        }
    };

    // 许可证文本特征（用于模糊匹配）
    const LICENSE_SIGNATURES = {
        'MIT': {
            required: ['permission is hereby granted', 'free of charge', 'as is'],
            optional: ['mit license', 'software and associated documentation files'],
            weight: 1.0
        },
        'Apache-2.0': {
            required: ['apache license', 'version 2.0', 'january 2004'],
            optional: ['licensed under the apache license', 'www.apache.org/licenses'],
            weight: 1.0
        },
        'GPL-3.0': {
            required: ['gnu general public license', 'version 3', '29 june 2007'],
            optional: ['free software foundation', 'any later version'],
            weight: 1.0
        },
        'BSD-3-Clause': {
            required: ['redistribution and use in source and binary forms', 'with or without modification'],
            optional: ['bsd 3-clause', 'copyright notice', 'list of conditions'],
            weight: 1.0
        }
    };

    /**
     * 模糊匹配算法 - 基于Levenshtein距离和N-gram
     */
    class FuzzyMatcher {
        constructor(options = {}) {
            this.threshold = options.threshold || 0.8;
            this.ngramSize = options.ngramSize || 3;
        }

        // 计算Levenshtein距离
        levenshteinDistance(str1, str2) {
            const matrix = [];
            for (let i = 0; i <= str2.length; i++) {
                matrix[i] = [i];
            }
            for (let j = 0; j <= str1.length; j++) {
                matrix[0][j] = j;
            }
            for (let i = 1; i <= str2.length; i++) {
                for (let j = 1; j <= str1.length; j++) {
                    if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                        matrix[i][j] = matrix[i - 1][j - 1];
                    } else {
                        matrix[i][j] = Math.min(
                            matrix[i - 1][j - 1] + 1,
                            matrix[i][j - 1] + 1,
                            matrix[i - 1][j] + 1
                        );
                    }
                }
            }
            return matrix[str2.length][str1.length];
        }

        // 计算相似度
        similarity(str1, str2) {
            const maxLength = Math.max(str1.length, str2.length);
            if (maxLength === 0) return 1.0;
            const distance = this.levenshteinDistance(str1, str2);
            return 1 - distance / maxLength;
        }

        // N-gram分词
        ngrams(text, n = this.ngramSize) {
            const grams = [];
            const normalized = text.toLowerCase().replace(/\s+/g, ' ').trim();
            for (let i = 0; i <= normalized.length - n; i++) {
                grams.push(normalized.substring(i, i + n));
            }
            return grams;
        }

        // N-gram相似度
        ngramSimilarity(str1, str2) {
            const grams1 = new Set(this.ngrams(str1));
            const grams2 = new Set(this.ngrams(str2));
            
            const intersection = new Set([...grams1].filter(x => grams2.has(x)));
            const union = new Set([...grams1, ...grams2]);
            
            return intersection.size / union.size;
        }

        // 综合匹配
        match(text, patterns) {
            const results = [];
            
            for (const [name, pattern] of Object.entries(patterns)) {
                let score = 0;
                let totalWeight = 0;

                // 检查必需特征
                for (const required of pattern.required || []) {
                    const sim = this.ngramSimilarity(text, required);
                    score += sim * 2; // 必需特征权重更高
                    totalWeight += 2;
                }

                // 检查可选特征
                for (const optional of pattern.optional || []) {
                    const sim = this.ngramSimilarity(text, optional);
                    score += sim;
                    totalWeight += 1;
                }

                const finalScore = totalWeight > 0 ? score / totalWeight : 0;
                
                results.push({
                    name,
                    score: finalScore * (pattern.weight || 1.0),
                    confidence: finalScore
                });
            }

            results.sort((a, b) => b.score - a.score);
            return results;
        }
    }

    /**
     * 增强版许可证检测器
     */
    class EnhancedLicenseDetector {
        constructor() {
            this.fuzzyMatcher = new FuzzyMatcher();
            this.cache = new Map();
            this.cacheExpiry = 3600000; // 1小时
        }

        // 从文本检测（多方法融合）
        async detectFromText(text, options = {}) {
            const cacheKey = this.hashText(text);
            
            // 检查缓存
            const cached = this.getFromCache(cacheKey);
            if (cached && !options.skipCache) {
                return cached;
            }

            const results = {
                methods: {},
                conclusions: [],
                confidence: 0,
                recommended: 'NOASSERTION'
            };

            // 方法1: 精确SPDX标识符匹配
            results.methods.exact = this.detectExactSPDX(text);

            // 方法2: 模糊特征匹配
            results.methods.fuzzy = this.detectFuzzy(text);

            // 方法3: 正则模式匹配
            results.methods.regex = this.detectRegex(text);

            // 融合结论
            const conclusion = this.fuseResults(results.methods);
            results.conclusions = conclusion.candidates;
            results.confidence = conclusion.confidence;
            results.recommended = conclusion.recommended;

            // 缓存结果
            this.setCache(cacheKey, results);

            return results;
        }

        // 精确SPDX匹配
        detectExactSPDX(text) {
            const spdxRegex = /SPDX-License-Identifier:\s*([\w\-\.]+)/gi;
            const matches = [];
            let match;

            while ((match = spdxRegex.exec(text)) !== null) {
                const identifier = match[1];
                if (SPDX_LICENSES[identifier]) {
                    matches.push({
                        identifier,
                        confidence: 1.0,
                        source: 'SPDX-Identifier',
                        position: match.index
                    });
                }
            }

            return matches;
        }

        // 模糊匹配
        detectFuzzy(text) {
            const normalized = text.toLowerCase();
            const matches = this.fuzzyMatcher.match(normalized, LICENSE_SIGNATURES);
            
            return matches
                .filter(m => m.confidence >= 0.6)
                .map(m => ({
                    identifier: m.name,
                    confidence: m.confidence,
                    source: 'fuzzy-match',
                    score: m.score
                }));
        }

        // 正则模式匹配
        detectRegex(text) {
            const patterns = {
                'MIT': /\bMIT\s+Licen[sc]e\b/i,
                'Apache-2.0': /Apache\s+Licen[sc]e[\s,]*Version\s+2\.0/i,
                'GPL-3.0': /GNU\s+General\s+Public\s+Licen[sc]e[\s,]*Version\s+3/i,
                'BSD-3-Clause': /BSD\s+3-Clause/i,
                'BSD-2-Clause': /BSD\s+2-Clause|Simplified\s+BSD/i
            };

            const matches = [];
            for (const [license, regex] of Object.entries(patterns)) {
                if (regex.test(text)) {
                    matches.push({
                        identifier: license,
                        confidence: 0.85,
                        source: 'regex-match'
                    });
                }
            }

            return matches;
        }

        // 结果融合
        fuseResults(methods) {
            const scores = new Map();

            // 汇总各方法结果
            for (const [method, results] of Object.entries(methods)) {
                for (const result of results) {
                    const current = scores.get(result.identifier) || { 
                        totalScore: 0, 
                        count: 0,
                        maxConfidence: 0,
                        sources: []
                    };
                    
                    current.totalScore += result.confidence;
                    current.count++;
                    current.maxConfidence = Math.max(current.maxConfidence, result.confidence);
                    current.sources.push(result.source);
                    
                    scores.set(result.identifier, current);
                }
            }

            // 计算最终分数
            const candidates = [];
            for (const [identifier, data] of scores) {
                const avgScore = data.totalScore / data.count;
                const boost = data.sources.includes('SPDX-Identifier') ? 0.2 : 0;
                
                candidates.push({
                    identifier,
                    confidence: Math.min(data.maxConfidence + boost, 1.0),
                    score: avgScore,
                    sources: data.sources,
                    methodCount: data.count
                });
            }

            candidates.sort((a, b) => b.confidence - a.confidence);

            return {
                candidates,
                confidence: candidates.length > 0 ? candidates[0].confidence : 0,
                recommended: candidates.length > 0 ? candidates[0].identifier : 'NOASSERTION'
            };
        }

        // 文本哈希
        hashText(text) {
            let hash = 0;
            for (let i = 0; i < text.length; i++) {
                const char = text.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            return hash.toString(16);
        }

        // 缓存操作
        getFromCache(key) {
            const item = this.cache.get(key);
            if (item && Date.now() - item.timestamp < this.cacheExpiry) {
                return item.data;
            }
            return null;
        }

        setCache(key, data) {
            this.cache.set(key, { data, timestamp: Date.now() });
        }
    }

    /**
     * 依赖树分析器
     */
    class DependencyTreeAnalyzer {
        constructor() {
            this.visited = new Set();
            this.cycles = [];
        }

        // 构建依赖树
        buildTree(dependencies, getChildrenFn) {
            const tree = {
                root: true,
                children: []
            };

            for (const [name, version] of Object.entries(dependencies)) {
                const node = this.buildNode(name, version, getChildrenFn, 0);
                if (node) {
                    tree.children.push(node);
                }
            }

            return tree;
        }

        // 构建节点
        buildNode(name, version, getChildrenFn, depth, path = []) {
            const id = `${name}@${version}`;
            
            // 检测循环依赖
            if (path.includes(id)) {
                this.cycles.push([...path, id]);
                return { name, version, circular: true };
            }

            // 限制深度
            if (depth > 10) {
                return { name, version, truncated: true };
            }

            const node = {
                name,
                version,
                depth,
                children: []
            };

            try {
                const children = getChildrenFn(name, version);
                for (const [childName, childVersion] of Object.entries(children || {})) {
                    const child = this.buildNode(
                        childName, 
                        childVersion, 
                        getChildrenFn, 
                        depth + 1,
                        [...path, id]
                    );
                    if (child) {
                        node.children.push(child);
                    }
                }
            } catch (error) {
                node.error = error.message;
            }

            return node;
        }

        // 扁平化依赖列表
        flatten(tree) {
            const flat = new Map();

            const traverse = (node) => {
                if (!node || node.circular) return;

                const id = `${node.name}@${node.version}`;
                
                if (!flat.has(id)) {
                    flat.set(id, {
                        name: node.name,
                        version: node.version,
                        depth: node.depth,
                        parents: []
                    });
                }

                const entry = flat.get(id);

                for (const child of node.children || []) {
                    if (!child.circular) {
                        entry.parents.push(child.name);
                        traverse(child);
                    }
                }
            };

            for (const child of tree.children || []) {
                traverse(child);
            }

            return flat;
        }

        // 查找许可证冲突
        findConflicts(flatDependencies, getLicenseFn, projectLicense) {
            const conflicts = [];

            for (const [id, dep] of flatDependencies) {
                const license = getLicenseFn(dep.name, dep.version);
                
                if (!license) continue;

                const compatibility = this.checkCompatibility(projectLicense, license);
                
                if (!compatible) {
                    conflicts.push({
                        dependency: id,
                        license,
                        projectLicense,
                        reason: compatibility.reason,
                        severity: compatibility.severity
                    });
                }
            }

            return conflicts;
        }

        // 检查兼容性
        checkCompatibility(projectLicense, depLicense) {
            const matrix = LICENSE_COMPATIBILITY_MATRIX[projectLicense];
            
            if (!matrix) {
                return { compatible: true, reason: 'Unknown project license' };
            }

            if (matrix.canCombineWith.includes(depLicense)) {
                return { compatible: true };
            }

            const depMatrix = LICENSE_COMPATIBILITY_MATRIX[depLicense];
            
            if (depMatrix?.strongCopyleft) {
                return {
                    compatible: false,
                    reason: `${depLicense} is strong copyleft and incompatible with ${projectLicense}`,
                    severity: 'high'
                };
            }

            if (depMatrix?.copyleft) {
                return {
                    compatible: false,
                    reason: `${depLicense} is copyleft and may be incompatible`,
                    severity: 'medium'
                };
            }

            return {
                compatible: false,
                reason: `License ${depLicense} is not compatible with ${projectLicense}`,
                severity: 'low'
            };
        }
    }

    /**
     * 增强版SBOM生成器（符合SPDX 2.3标准）
     */
    class EnhancedSBOMGenerator {
        constructor() {
            this.detector = new EnhancedLicenseDetector();
        }

        // 生成SPDX格式的SBOM
        async generateSPDX(projectFiles, options = {}) {
            const spdxVersion = 'SPDX-2.3';
            const documentNamespace = options.namespace || 
                `https://kaelis.io/spdx/${options.projectName || 'project'}-${Date.now()}`;

            const sbom = {
                spdxVersion,
                dataLicense: 'CC0-1.0',
                SPDXID: 'SPDXRef-DOCUMENT',
                name: options.projectName || 'Unnamed Project',
                documentNamespace,
                creationInfo: {
                    created: new Date().toISOString(),
                    creators: [
                        `Tool: Kaelis-SBOM-Generator-1.0.0`,
                        options.organization ? `Organization: ${options.organization}` : null
                    ].filter(Boolean)
                },
                packages: [],
                relationships: []
            };

            // 添加项目包
            const projectPackage = {
                SPDXID: 'SPDXRef-Project',
                name: options.projectName || 'Project',
                downloadLocation: options.downloadLocation || 'NOASSERTION',
                filesAnalyzed: false,
                verificationCode: null,
                licenseConcluded: options.projectLicense || 'NOASSERTION',
                licenseDeclared: options.projectLicense || 'NOASSERTION',
                copyrightText: options.copyright || 'NOASSERTION'
            };
            sbom.packages.push(projectPackage);

            // 解析依赖
            const deps = await this.extractDependencies(projectFiles);
            
            for (let i = 0; i < deps.length; i++) {
                const dep = deps[i];
                const spdxId = `SPDXRef-Package-${i}`;
                
                // 检测许可证
                const licenseResult = await this.detector.detectFromText(
                    dep.licenseText || ''
                );

                const packageInfo = {
                    SPDXID: spdxId,
                    name: dep.name,
                    versionInfo: dep.version,
                    downloadLocation: dep.downloadLocation || 'NOASSERTION',
                    filesAnalyzed: false,
                    licenseConcluded: licenseResult.recommended,
                    licenseDeclared: dep.declaredLicense || licenseResult.recommended,
                    copyrightText: 'NOASSERTION',
                    externalRefs: dep.purl ? [{
                        referenceCategory: 'PACKAGE-MANAGER',
                        referenceType: 'purl',
                        referenceLocator: dep.purl
                    }] : []
                };

                sbom.packages.push(packageInfo);

                // 添加关系
                sbom.relationships.push({
                    spdxElementId: 'SPDXRef-Project',
                    relatedSpdxElement: spdxId,
                    relationshipType: 'DEPENDS_ON'
                });
            }

            return sbom;
        }

        // 提取依赖
        async extractDependencies(projectFiles) {
            const deps = [];

            // 解析package.json
            const packageJsonFile = projectFiles.find(f => f.name === 'package.json');
            if (packageJsonFile) {
                try {
                    const content = await packageJsonFile.text();
                    const packageJson = JSON.parse(content);
                    
                    const allDeps = {
                        ...packageJson.dependencies,
                        ...packageJson.devDependencies,
                        ...packageJson.peerDependencies
                    };

                    for (const [name, version] of Object.entries(allDeps || {})) {
                        deps.push({
                            name,
                            version: version.replace(/^[\^~]/, ''),
                            purl: `pkg:npm/${name}@${version}`,
                            declaredLicense: null,
                            licenseText: null
                        });
                    }
                } catch (error) {
                    console.error('[EnhancedSBOMGenerator] package.json解析失败:', error);
                }
            }

            return deps;
        }

        // 导出为SPDX Tag-Value格式
        exportTagValue(sbom) {
            const lines = [
                `SPDXVersion: ${sbom.spdxVersion}`,
                `DataLicense: ${sbom.dataLicense}`,
                `SPDXID: ${sbom.SPDXID}`,
                `DocumentName: ${sbom.name}`,
                `DocumentNamespace: ${sbom.documentNamespace}`,
                ``,
                `## Creation Info`,
                `Creator: ${sbom.creationInfo.creators.join('\nCreator: ')}`,
                `Created: ${sbom.creationInfo.created}`,
                ``
            ];

            for (const pkg of sbom.packages) {
                lines.push(`## Package: ${pkg.name}`);
                lines.push(`PackageName: ${pkg.name}`);
                lines.push(`SPDXID: ${pkg.SPDXID}`);
                lines.push(`PackageVersion: ${pkg.versionInfo || 'NOASSERTION'}`);
                lines.push(`PackageDownloadLocation: ${pkg.downloadLocation}`);
                lines.push(`FilesAnalyzed: ${pkg.filesAnalyzed}`);
                lines.push(`PackageLicenseConcluded: ${pkg.licenseConcluded}`);
                lines.push(`PackageLicenseDeclared: ${pkg.licenseDeclared}`);
                lines.push(`PackageCopyrightText: ${pkg.copyrightText}`);
                lines.push('');
            }

            return lines.join('\n');
        }

        // 导出为SPDX JSON格式
        exportJSON(sbom) {
            return JSON.stringify(sbom, null, 2);
        }
    }

    // 导出 - UMD格式
    const exports = {
        EnhancedLicenseDetector,
        FuzzyMatcher,
        DependencyTreeAnalyzer,
        EnhancedSBOMGenerator,
        SPDX_LICENSES,
        LICENSE_COMPATIBILITY_MATRIX
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.OpenSourceMatcher = exports;
        // 保持向后兼容
        window.EnhancedOpenSourceMatcher = exports;
    }

    console.log('[EnhancedOpenSourceMatcher] 增强版开源匹配模块已加载');
})();
