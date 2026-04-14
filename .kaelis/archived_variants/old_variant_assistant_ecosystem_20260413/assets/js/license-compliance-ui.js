/**
 * Kaelis License Compliance UI
 * 许可证合规性UI模块 - 提供可视化界面进行开源合规检查
 */

(function() {
    'use strict';

    /**
     * 许可证合规性面板
     */
    class LicenseCompliancePanel {
        constructor(containerId) {
            this.container = document.getElementById(containerId);
            this.checker = new window.OpenSourceMatcher.LicenseComplianceChecker();
            this.sbomGenerator = new window.OpenSourceMatcher.SBOMGenerator();
            this.currentReport = null;
            
            this.init();
        }

        init() {
            this.render();
            this.bindEvents();
        }

        render() {
            if (!this.container) return;

            this.container.innerHTML = `
                <div class="license-compliance-panel">
                    <div class="panel-header">
                        <h3>开源许可证合规性检查</h3>
                        <p class="panel-description">检测项目中的开源组件和许可证兼容性</p>
                    </div>
                    
                    <div class="upload-section">
                        <div class="upload-area" id="license-upload-area">
                            <div class="upload-icon">📁</div>
                            <p>拖拽项目文件到此处，或点击选择</p>
                            <input type="file" id="license-file-input" webkitdirectory directory multiple style="display: none;">
                            <button class="btn btn-primary" id="btn-select-files">选择项目文件夹</button>
                        </div>
                    </div>

                    <div class="project-config" id="project-config" style="display: none;">
                        <h4>项目配置</h4>
                        <div class="form-group">
                            <label>项目许可证</label>
                            <select id="project-license-select">
                                <option value="MIT">MIT</option>
                                <option value="Apache-2.0">Apache-2.0</option>
                                <option value="GPL-3.0">GPL-3.0</option>
                                <option value="BSD-3-Clause">BSD-3-Clause</option>
                                <option value="Proprietary">专有软件</option>
                            </select>
                        </div>
                        <button class="btn btn-primary" id="btn-start-check">开始检查</button>
                    </div>

                    <div class="check-progress" id="check-progress" style="display: none;">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progress-fill"></div>
                        </div>
                        <p id="progress-text">正在分析...</p>
                    </div>

                    <div class="results-section" id="results-section" style="display: none;">
                        <div class="results-header">
                            <h4>检查结果</h4>
                            <div class="results-actions">
                                <button class="btn btn-secondary" id="btn-export-sbom">导出SBOM</button>
                                <button class="btn btn-secondary" id="btn-export-report">导出报告</button>
                            </div>
                        </div>

                        <div class="summary-cards">
                            <div class="summary-card status-${this.currentReport?.violations.length > 0 ? 'error' : 'success'}">
                                <div class="card-icon">${this.currentReport?.violations.length > 0 ? '⚠️' : '✅'}</div>
                                <div class="card-content">
                                    <span class="card-value">${this.currentReport?.violations.length || 0}</span>
                                    <span class="card-label">违规</span>
                                </div>
                            </div>
                            <div class="summary-card">
                                <div class="card-icon">📦</div>
                                <div class="card-content">
                                    <span class="card-value" id="component-count">0</span>
                                    <span class="card-label">组件</span>
                                </div>
                            </div>
                            <div class="summary-card">
                                <div class="card-icon">📄</div>
                                <div class="card-content">
                                    <span class="card-value" id="license-count">0</span>
                                    <span class="card-label">许可证</span>
                                </div>
                            </div>
                        </div>

                        <div class="results-tabs">
                            <button class="tab-btn active" data-tab="components">组件列表</button>
                            <button class="tab-btn" data-tab="violations">违规详情</button>
                            <button class="tab-btn" data-tab="licenses">许可证</button>
                        </div>

                        <div class="tab-content" id="tab-components">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>组件</th>
                                        <th>版本</th>
                                        <th>许可证</th>
                                        <th>状态</th>
                                    </tr>
                                </thead>
                                <tbody id="components-tbody"></tbody>
                            </table>
                        </div>

                        <div class="tab-content" id="tab-violations" style="display: none;">
                            <div id="violations-list"></div>
                        </div>

                        <div class="tab-content" id="tab-licenses" style="display: none;">
                            <div id="licenses-list"></div>
                        </div>
                    </div>
                </div>
            `;
        }

        bindEvents() {
            // 文件选择
            const uploadArea = this.container.querySelector('#license-upload-area');
            const fileInput = this.container.querySelector('#license-file-input');
            const selectBtn = this.container.querySelector('#btn-select-files');

            selectBtn?.addEventListener('click', () => fileInput?.click());

            fileInput?.addEventListener('change', (e) => {
                this.handleFileSelect(e.target.files);
            });

            // 拖拽上传
            uploadArea?.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });

            uploadArea?.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea?.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                this.handleFileSelect(e.dataTransfer.files);
            });

            // 开始检查
            const startBtn = this.container.querySelector('#btn-start-check');
            startBtn?.addEventListener('click', () => this.startCheck());

            // 标签切换
            const tabBtns = this.container.querySelectorAll('.tab-btn');
            tabBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const tab = btn.dataset.tab;
                    this.switchTab(tab);
                });
            });

            // 导出按钮
            const exportSbomBtn = this.container.querySelector('#btn-export-sbom');
            exportSbomBtn?.addEventListener('click', () => this.exportSBOM());

            const exportReportBtn = this.container.querySelector('#btn-export-report');
            exportReportBtn?.addEventListener('click', () => this.exportReport());
        }

        handleFileSelect(files) {
            this.projectFiles = Array.from(files);
            
            // 显示配置区域
            const configSection = this.container.querySelector('#project-config');
            if (configSection) {
                configSection.style.display = 'block';
            }

            // 自动检测项目许可证
            this.detectProjectLicense();
        }

        async detectProjectLicense() {
            const detector = new window.OpenSourceMatcher.LicenseDetector();
            const result = await detector.detectLicenseFile(this.projectFiles);
            
            if (result.license !== 'Unknown') {
                const select = this.container.querySelector('#project-license-select');
                if (select) {
                    select.value = result.license;
                }
            }
        }

        async startCheck() {
            const licenseSelect = this.container.querySelector('#project-license-select');
            const projectLicense = licenseSelect?.value || 'MIT';

            // 显示进度
            const progressSection = this.container.querySelector('#check-progress');
            const progressFill = this.container.querySelector('#progress-fill');
            const progressText = this.container.querySelector('#progress-text');
            
            progressSection.style.display = 'block';

            // 模拟进度
            let progress = 0;
            const interval = setInterval(() => {
                progress += 10;
                if (progressFill) progressFill.style.width = `${progress}%`;
                
                if (progress >= 100) {
                    clearInterval(interval);
                }
            }, 100);

            try {
                // 执行检查
                this.currentReport = await this.checker.checkProject(
                    this.projectFiles,
                    projectLicense
                );

                clearInterval(interval);
                if (progressFill) progressFill.style.width = '100%';

                // 显示结果
                this.showResults();

            } catch (error) {
                console.error('[LicenseCompliancePanel] 检查失败:', error);
                progressText.textContent = '检查失败: ' + error.message;
            }
        }

        showResults() {
            const resultsSection = this.container.querySelector('#results-section');
            resultsSection.style.display = 'block';

            // 更新统计
            document.getElementById('component-count').textContent = 
                this.currentReport.components.length;
            document.getElementById('license-count').textContent = 
                this.currentReport.detectedLicenses.length;

            // 渲染组件列表
            this.renderComponents();

            // 渲染违规
            this.renderViolations();

            // 渲染许可证
            this.renderLicenses();
        }

        renderComponents() {
            const tbody = document.getElementById('components-tbody');
            if (!tbody) return;

            tbody.innerHTML = this.currentReport.components.map(comp => {
                const isViolation = this.currentReport.violations.some(
                    v => v.component === comp.name
                );

                return `
                    <tr>
                        <td>${comp.name}</td>
                        <td>${comp.version || 'unknown'}</td>
                        <td><span class="license-badge">${comp.license}</span></td>
                        <td>
                            ${isViolation 
                                ? '<span class="status-badge error">不兼容</span>' 
                                : '<span class="status-badge success">兼容</span>'}
                        </td>
                    </tr>
                `;
            }).join('');
        }

        renderViolations() {
            const container = document.getElementById('violations-list');
            if (!container) return;

            if (this.currentReport.violations.length === 0) {
                container.innerHTML = '<p class="no-violations">✅ 未发现许可证违规</p>';
                return;
            }

            container.innerHTML = this.currentReport.violations.map(v => `
                <div class="violation-item">
                    <div class="violation-header">
                        <span class="violation-type">${v.type}</span>
                        <span class="violation-component">${v.component}</span>
                    </div>
                    <p class="violation-reason">${v.reason}</p>
                    <div class="violation-licenses">
                        <span>项目: ${v.projectLicense}</span>
                        <span>→</span>
                        <span>组件: ${v.componentLicense}</span>
                    </div>
                </div>
            `).join('');
        }

        renderLicenses() {
            const container = document.getElementById('licenses-list');
            if (!container) return;

            const allLicenses = [
                ...this.currentReport.detectedLicenses,
                ...this.currentReport.components.map(c => ({
                    license: c.license,
                    source: c.name,
                    confidence: 1.0
                }))
            ];

            // 去重
            const uniqueLicenses = [...new Map(allLicenses.map(l => [l.license, l])).values()];

            container.innerHTML = uniqueLicenses.map(l => `
                <div class="license-item">
                    <span class="license-name">${l.license}</span>
                    <span class="license-source">来源: ${l.source}</span>
                    ${l.confidence < 1 ? `<span class="license-confidence">置信度: ${(l.confidence * 100).toFixed(1)}%</span>` : ''}
                </div>
            `).join('');
        }

        switchTab(tab) {
            // 切换按钮状态
            this.container.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.tab === tab);
            });

            // 切换内容
            this.container.querySelectorAll('.tab-content').forEach(content => {
                content.style.display = 'none';
            });

            const selectedContent = document.getElementById(`tab-${tab}`);
            if (selectedContent) {
                selectedContent.style.display = 'block';
            }
        }

        async exportSBOM() {
            if (!this.projectFiles) return;

            const sbom = await this.sbomGenerator.generateSBOM(this.projectFiles, {
                projectName: 'My Project',
                projectVersion: '1.0.0'
            });

            const content = this.sbomGenerator.exportSBOM(sbom, 'json');
            this.downloadFile(content, 'sbom.json', 'application/json');
        }

        exportReport() {
            if (!this.currentReport) return;

            const report = this.checker.generateReport(this.currentReport);
            this.downloadFile(report, 'license-compliance-report.md', 'text/markdown');
        }

        downloadFile(content, filename, type) {
            const blob = new Blob([content], { type });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
    }

    // 导出 - UMD格式
    const exports = {
        LicenseCompliancePanel
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.LicenseComplianceUI = exports;
        // 保持向后兼容
        window.LicenseComplianceUI = exports;
    }

    console.log('[LicenseComplianceUI] 许可证合规性UI已加载');
})();
