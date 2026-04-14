/**
 * Kaelis Binary Result Handler
 * 二进制结果传输 - Base64编码
 * 支持文件、图片等二进制数据传输
 */

(function() {
    'use strict';

    // 结果类型
    const RESULT_TYPE = {
        JSON: 'json',
        TEXT: 'text',
        BINARY: 'binary',
        FILE: 'file',
        IMAGE: 'image',
        AUDIO: 'audio',
        VIDEO: 'video'
    };

    // MIME类型映射
    const MIME_TYPES = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
        'pdf': 'application/pdf',
        'txt': 'text/plain',
        'json': 'application/json',
        'csv': 'text/csv',
        'zip': 'application/zip',
        'mp3': 'audio/mpeg',
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'wav': 'audio/wav'
    };

    /**
     * 二进制结果处理器
     */
    class BinaryResultHandler {
        constructor(options = {}) {
            this.maxSize = options.maxSize || 10 * 1024 * 1024; // 默认10MB
            this.chunkSize = options.chunkSize || 64 * 1024;    // 64KB分片
            this.enableCompression = options.enableCompression !== false;
        }

        // 文件转Base64
        async fileToBase64(file) {
            return new Promise((resolve, reject) => {
                if (file.size > this.maxSize) {
                    reject(new Error(`File size ${file.size} exceeds maximum ${this.maxSize}`));
                    return;
                }

                const reader = new FileReader();
                reader.onload = () => {
                    const base64 = reader.result.split(',')[1];
                    resolve(base64);
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }

        // Base64转文件
        base64ToFile(base64, filename, mimeType) {
            const byteString = atob(base64);
            const ab = new ArrayBuffer(byteString.length);
            const ia = new Uint8Array(ab);

            for (let i = 0; i < byteString.length; i++) {
                ia[i] = byteString.charCodeAt(i);
            }

            return new File([ab], filename, { type: mimeType });
        }

        // 创建结果对象
        createResult(data, options = {}) {
            const type = options.type || this.detectType(data, options.filename);
            const mimeType = options.mimeType || MIME_TYPES[type] || 'application/octet-stream';

            if (type === RESULT_TYPE.JSON || type === RESULT_TYPE.TEXT) {
                return {
                    type,
                    mimeType,
                    data: typeof data === 'string' ? data : JSON.stringify(data),
                    size: JSON.stringify(data).length
                };
            }

            // 二进制数据
            return {
                type,
                mimeType,
                filename: options.filename || `result_${Date.now()}`,
                data: data, // Base64编码
                size: data.length,
                encoding: 'base64',
                compressed: options.compressed || false
            };
        }

        // 检测数据类型
        detectType(data, filename) {
            if (typeof data === 'object' && !(data instanceof File)) {
                return RESULT_TYPE.JSON;
            }

            if (filename) {
                const ext = filename.split('.').pop().toLowerCase();
                if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) {
                    return RESULT_TYPE.IMAGE;
                }
                if (['mp3', 'wav', 'ogg'].includes(ext)) {
                    return RESULT_TYPE.AUDIO;
                }
                if (['mp4', 'webm', 'avi'].includes(ext)) {
                    return RESULT_TYPE.VIDEO;
                }
                if (['pdf', 'zip', 'doc', 'docx'].includes(ext)) {
                    return RESULT_TYPE.FILE;
                }
            }

            return RESULT_TYPE.BINARY;
        }

        // 分片编码（大文件）
        async encodeInChunks(file, onProgress = null) {
            const chunks = [];
            const totalChunks = Math.ceil(file.size / this.chunkSize);

            for (let i = 0; i < totalChunks; i++) {
                const start = i * this.chunkSize;
                const end = Math.min(start + this.chunkSize, file.size);
                const chunk = file.slice(start, end);

                const base64 = await this.fileToBase64(chunk);
                chunks.push({
                    index: i,
                    total: totalChunks,
                    data: base64
                });

                if (onProgress) {
                    onProgress({
                        loaded: end,
                        total: file.size,
                        percent: Math.round((end / file.size) * 100)
                    });
                }
            }

            return {
                filename: file.name,
                mimeType: file.type,
                size: file.size,
                totalChunks,
                chunks
            };
        }

        // 分片解码
        decodeFromChunks(chunkedData) {
            const { chunks, filename, mimeType } = chunkedData;
            
            // 按顺序合并
            chunks.sort((a, b) => a.index - b.index);
            const base64 = chunks.map(c => c.data).join('');

            return this.base64ToFile(base64, filename, mimeType);
        }

        // 压缩数据（简单实现）
        compress(data) {
            // 实际实现应使用pako等压缩库
            // 这里仅作标记
            return {
                compressed: true,
                algorithm: 'gzip',
                data: data
            };
        }

        // 解压数据
        decompress(compressedData) {
            // 实际实现应使用pako等压缩库
            return compressedData.data;
        }

        // 创建下载链接
        createDownloadLink(result) {
            if (result.type === RESULT_TYPE.JSON || result.type === RESULT_TYPE.TEXT) {
                const blob = new Blob([result.data], { type: result.mimeType });
                return URL.createObjectURL(blob);
            }

            const file = this.base64ToFile(result.data, result.filename, result.mimeType);
            return URL.createObjectURL(file);
        }

        // 预览结果
        previewResult(result, container) {
            if (!container) return;

            container.innerHTML = '';

            switch (result.type) {
                case RESULT_TYPE.IMAGE:
                    const img = document.createElement('img');
                    img.src = `data:${result.mimeType};base64,${result.data}`;
                    img.style.maxWidth = '100%';
                    img.style.maxHeight = '400px';
                    container.appendChild(img);
                    break;

                case RESULT_TYPE.AUDIO:
                    const audio = document.createElement('audio');
                    audio.controls = true;
                    audio.src = `data:${result.mimeType};base64,${result.data}`;
                    container.appendChild(audio);
                    break;

                case RESULT_TYPE.VIDEO:
                    const video = document.createElement('video');
                    video.controls = true;
                    video.style.maxWidth = '100%';
                    video.src = `data:${result.mimeType};base64,${result.data}`;
                    container.appendChild(video);
                    break;

                case RESULT_TYPE.PDF:
                    const iframe = document.createElement('iframe');
                    iframe.src = `data:${result.mimeType};base64,${result.data}`;
                    iframe.style.width = '100%';
                    iframe.style.height = '500px';
                    container.appendChild(iframe);
                    break;

                case RESULT_TYPE.JSON:
                    const pre = document.createElement('pre');
                    pre.textContent = JSON.stringify(JSON.parse(result.data), null, 2);
                    pre.style.overflow = 'auto';
                    pre.style.maxHeight = '400px';
                    container.appendChild(pre);
                    break;

                default:
                    const downloadBtn = document.createElement('a');
                    downloadBtn.href = this.createDownloadLink(result);
                    downloadBtn.download = result.filename || 'download';
                    downloadBtn.className = 'btn btn-primary';
                    downloadBtn.textContent = `下载 ${result.filename || '文件'}`;
                    container.appendChild(downloadBtn);
            }
        }
    }

    /**
     * 结果传输管理器
     */
    class ResultTransferManager {
        constructor(options = {}) {
            this.handler = new BinaryResultHandler(options);
            this.pendingTransfers = new Map();
            this.completedTransfers = new Map();
        }

        // 发送结果
        async sendResult(wsClient, taskId, data, options = {}) {
            const size = JSON.stringify(data).length;

            // 小数据直接发送
            if (size < this.handler.chunkSize) {
                const result = this.handler.createResult(data, options);
                wsClient.send({
                    type: 'task_result',
                    payload: {
                        taskId,
                        result,
                        complete: true
                    }
                });
                return;
            }

            // 大数据分片发送
            await this.sendInChunks(wsClient, taskId, data, options);
        }

        // 分片发送
        async sendInChunks(wsClient, taskId, file, options = {}) {
            const chunked = await this.handler.encodeInChunks(file, (progress) => {
                wsClient.send({
                    type: 'transfer_progress',
                    payload: { taskId, progress }
                });
            });

            // 发送元数据
            wsClient.send({
                type: 'transfer_start',
                payload: {
                    taskId,
                    metadata: {
                        filename: chunked.filename,
                        mimeType: chunked.mimeType,
                        size: chunked.size,
                        totalChunks: chunked.totalChunks
                    }
                }
            });

            // 发送分片
            for (const chunk of chunked.chunks) {
                wsClient.send({
                    type: 'transfer_chunk',
                    payload: {
                        taskId,
                        chunk
                    }
                });

                // 控制发送速率
                await new Promise(resolve => setTimeout(resolve, 10));
            }

            // 发送完成
            wsClient.send({
                type: 'transfer_complete',
                payload: { taskId }
            });
        }

        // 接收分片
        receiveChunk(taskId, chunk) {
            if (!this.pendingTransfers.has(taskId)) {
                this.pendingTransfers.set(taskId, {
                    chunks: [],
                    metadata: null,
                    receivedChunks: 0
                });
            }

            const transfer = this.pendingTransfers.get(taskId);
            transfer.chunks.push(chunk);
            transfer.receivedChunks++;

            return transfer;
        }

        // 设置传输元数据
        setTransferMetadata(taskId, metadata) {
            if (!this.pendingTransfers.has(taskId)) {
                this.pendingTransfers.set(taskId, {
                    chunks: [],
                    metadata: null,
                    receivedChunks: 0
                });
            }

            this.pendingTransfers.get(taskId).metadata = metadata;
        }

        // 完成传输
        completeTransfer(taskId) {
            const transfer = this.pendingTransfers.get(taskId);
            if (!transfer) return null;

            const result = this.handler.decodeFromChunks({
                chunks: transfer.chunks,
                filename: transfer.metadata.filename,
                mimeType: transfer.metadata.mimeType
            });

            this.completedTransfers.set(taskId, result);
            this.pendingTransfers.delete(taskId);

            return result;
        }

        // 获取结果
        getResult(taskId) {
            return this.completedTransfers.get(taskId);
        }
    }

    // 导出 - UMD格式
    const exports = {
        BinaryResultHandler,
        ResultTransferManager,
        RESULT_TYPE,
        MIME_TYPES
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.BinaryResultHandler = exports;
        // 保持向后兼容
        window.BinaryResultHandler = exports;
    }

    console.log('[BinaryResultHandler] 二进制结果处理器已加载');
})();
