/**
 * Kaelis Binary Transfer Advanced
 * 二进制传输高级功能 - 压缩、加密、断点续传、多文件批量传输
 */

(function() {
    'use strict';

    // 压缩算法
    const COMPRESSION_ALGORITHM = {
        GZIP: 'gzip',
        DEFLATE: 'deflate',
        BROTLI: 'brotli',
        NONE: 'none'
    };

    // 加密算法
    const ENCRYPTION_ALGORITHM = {
        AES_GCM: 'AES-GCM',
        AES_CBC: 'AES-CBC',
        NONE: 'none'
    };

    // 传输状态
    const TRANSFER_STATE = {
        PENDING: 'pending',
        UPLOADING: 'uploading',
        PAUSED: 'paused',
        COMPLETED: 'completed',
        FAILED: 'failed',
        CANCELLED: 'cancelled'
    };

    /**
     * 压缩管理器
     */
    class CompressionManager {
        constructor() {
            this.algorithm = COMPRESSION_ALGORITHM.GZIP;
            this.compressionLevel = 6; // 1-9
        }

        // 检测是否支持CompressionStream API
        isSupported() {
            return typeof CompressionStream !== 'undefined';
        }

        // 压缩数据
        async compress(data, algorithm = this.algorithm) {
            if (!this.isSupported()) {
                return { data, compressed: false, algorithm: 'none' };
            }

            try {
                const blob = new Blob([data]);
                const compressedStream = blob.stream().pipeThrough(
                    new CompressionStream(algorithm)
                );
                
                const compressedBlob = await new Response(compressedStream).blob();
                const compressedArray = new Uint8Array(await compressedBlob.arrayBuffer());
                
                // Base64编码
                const base64 = btoa(String.fromCharCode(...compressedArray));
                
                return {
                    data: base64,
                    compressed: true,
                    algorithm,
                    originalSize: data.length,
                    compressedSize: base64.length,
                    ratio: (base64.length / data.length * 100).toFixed(2) + '%'
                };
            } catch (error) {
                console.error('[CompressionManager] 压缩失败:', error);
                return { data, compressed: false, algorithm: 'none' };
            }
        }

        // 解压数据
        async decompress(base64Data, algorithm = this.algorithm) {
            if (!this.isSupported()) {
                return base64Data;
            }

            try {
                // Base64解码
                const compressedArray = Uint8Array.from(atob(base64Data), c => c.charCodeAt(0));
                const blob = new Blob([compressedArray]);
                
                const decompressedStream = blob.stream().pipeThrough(
                    new DecompressionStream(algorithm)
                );
                
                const decompressedBlob = await new Response(decompressedStream).blob();
                const decompressedArray = new Uint8Array(await decompressedBlob.arrayBuffer());
                
                return new TextDecoder().decode(decompressedArray);
            } catch (error) {
                console.error('[CompressionManager] 解压失败:', error);
                return base64Data;
            }
        }

        // 智能压缩（根据内容类型选择）
        async smartCompress(data, mimeType) {
            // 已压缩格式跳过
            const compressedTypes = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'video/', 'audio/', 'application/zip', 'application/gzip',
                'application/pdf'
            ];
            
            if (compressedTypes.some(type => mimeType.includes(type))) {
                return { data, compressed: false, reason: 'already_compressed' };
            }

            return this.compress(data);
        }
    }

    /**
     * 加密管理器
     */
    class EncryptionManager {
        constructor() {
            this.algorithm = ENCRYPTION_ALGORITHM.AES_GCM;
            this.keyLength = 256;
        }

        // 生成密钥
        async generateKey() {
            return await crypto.subtle.generateKey(
                {
                    name: this.algorithm,
                    length: this.keyLength
                },
                true,
                ['encrypt', 'decrypt']
            );
        }

        // 从密码派生密钥
        async deriveKey(password, salt) {
            const encoder = new TextEncoder();
            const passwordData = encoder.encode(password);
            
            const keyMaterial = await crypto.subtle.importKey(
                'raw',
                passwordData,
                'PBKDF2',
                false,
                ['deriveBits', 'deriveKey']
            );

            return await crypto.subtle.deriveKey(
                {
                    name: 'PBKDF2',
                    salt: salt,
                    iterations: 100000,
                    hash: 'SHA-256'
                },
                keyMaterial,
                {
                    name: this.algorithm,
                    length: this.keyLength
                },
                false,
                ['encrypt', 'decrypt']
            );
        }

        // 加密数据
        async encrypt(data, key) {
            const encoder = new TextEncoder();
            const dataBuffer = encoder.encode(data);
            
            // 生成IV
            const iv = crypto.getRandomValues(new Uint8Array(12));
            
            const encrypted = await crypto.subtle.encrypt(
                {
                    name: this.algorithm,
                    iv: iv
                },
                key,
                dataBuffer
            );

            // 合并IV和加密数据
            const result = new Uint8Array(iv.length + encrypted.byteLength);
            result.set(iv);
            result.set(new Uint8Array(encrypted), iv.length);

            // Base64编码
            return btoa(String.fromCharCode(...result));
        }

        // 解密数据
        async decrypt(encryptedBase64, key) {
            const encryptedData = Uint8Array.from(atob(encryptedBase64), c => c.charCodeAt(0));
            
            // 提取IV
            const iv = encryptedData.slice(0, 12);
            const data = encryptedData.slice(12);

            const decrypted = await crypto.subtle.decrypt(
                {
                    name: this.algorithm,
                    iv: iv
                },
                key,
                data
            );

            return new TextDecoder().decode(decrypted);
        }

        // 导出密钥
        async exportKey(key) {
            const exported = await crypto.subtle.exportKey('raw', key);
            return btoa(String.fromCharCode(...new Uint8Array(exported)));
        }

        // 导入密钥
        async importKey(base64Key) {
            const keyData = Uint8Array.from(atob(base64Key), c => c.charCodeAt(0));
            return await crypto.subtle.importKey(
                'raw',
                keyData,
                this.algorithm,
                true,
                ['encrypt', 'decrypt']
            );
        }
    }

    /**
     * 断点续传管理器
     */
    class ResumableUploadManager {
        constructor(options = {}) {
            this.chunkSize = options.chunkSize || 1024 * 1024; // 1MB
            this.maxRetries = options.maxRetries || 3;
            this.concurrentChunks = options.concurrentChunks || 3;
            
            this.uploads = new Map();
            this.storageKey = 'kaelis_resumable_uploads';
            this.loadPersistedUploads();
        }

        // 创建上传任务
        async createUpload(file, options = {}) {
            const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            // 计算文件指纹（用于识别同一文件）
            const fingerprint = await this.calculateFingerprint(file);
            
            const upload = {
                id: uploadId,
                fileName: file.name,
                fileSize: file.size,
                fileType: file.type,
                fingerprint: fingerprint,
                chunkSize: this.chunkSize,
                totalChunks: Math.ceil(file.size / this.chunkSize),
                uploadedChunks: new Set(),
                failedChunks: new Set(),
                state: TRANSFER_STATE.PENDING,
                progress: 0,
                createdAt: Date.now(),
                updatedAt: Date.now(),
                options: options
            };

            this.uploads.set(uploadId, upload);
            this.persistUploads();
            
            return uploadId;
        }

        // 计算文件指纹
        async calculateFingerprint(file) {
            const arrayBuffer = await file.slice(0, Math.min(file.size, 1024 * 1024)).arrayBuffer();
            const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
            return btoa(String.fromCharCode(...new Uint8Array(hashBuffer)));
        }

        // 开始/恢复上传
        async startUpload(uploadId, uploadFn, onProgress = null) {
            const upload = this.uploads.get(uploadId);
            if (!upload) throw new Error('Upload not found');

            upload.state = TRANSFER_STATE.UPLOADING;
            upload.updatedAt = Date.now();

            const file = upload.file || await this.getFileFromInput(upload);
            upload.file = file;

            // 计算需要上传的分片
            const pendingChunks = [];
            for (let i = 0; i < upload.totalChunks; i++) {
                if (!upload.uploadedChunks.has(i)) {
                    pendingChunks.push(i);
                }
            }

            // 并发上传
            const semaphore = new Semaphore(this.concurrentChunks);
            const promises = pendingChunks.map(chunkIndex => 
                this.uploadChunk(upload, chunkIndex, file, uploadFn, semaphore)
            );

            // 等待所有分片上传完成
            await Promise.all(promises);

            // 检查是否全部完成
            if (upload.uploadedChunks.size === upload.totalChunks) {
                upload.state = TRANSFER_STATE.COMPLETED;
                upload.progress = 100;
                
                // 通知服务器合并
                await this.notifyComplete(uploadId, uploadFn);
            }

            this.persistUploads();
            return upload;
        }

        // 上传单个分片
        async uploadChunk(upload, chunkIndex, file, uploadFn, semaphore) {
            return semaphore.acquire().then(async () => {
                try {
                    const start = chunkIndex * upload.chunkSize;
                    const end = Math.min(start + upload.chunkSize, file.size);
                    const chunk = file.slice(start, end);

                    // 读取分片数据
                    const arrayBuffer = await chunk.arrayBuffer();
                    const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));

                    // 上传分片（带重试）
                    let retries = 0;
                    while (retries < this.maxRetries) {
                        try {
                            await uploadFn({
                                uploadId: upload.id,
                                chunkIndex,
                                totalChunks: upload.totalChunks,
                                data: base64,
                                checksum: await this.calculateChecksum(arrayBuffer)
                            });

                            upload.uploadedChunks.add(chunkIndex);
                            upload.failedChunks.delete(chunkIndex);
                            upload.progress = Math.round(
                                (upload.uploadedChunks.size / upload.totalChunks) * 100
                            );
                            upload.updatedAt = Date.now();
                            
                            this.persistUploads();
                            break;
                        } catch (error) {
                            retries++;
                            if (retries >= this.maxRetries) {
                                upload.failedChunks.add(chunkIndex);
                                throw error;
                            }
                            await sleep(1000 * retries); // 指数退避
                        }
                    }
                } finally {
                    semaphore.release();
                }
            });
        }

        // 计算校验和
        async calculateChecksum(arrayBuffer) {
            const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
            return btoa(String.fromCharCode(...new Uint8Array(hashBuffer)));
        }

        // 暂停上传
        pauseUpload(uploadId) {
            const upload = this.uploads.get(uploadId);
            if (upload && upload.state === TRANSFER_STATE.UPLOADING) {
                upload.state = TRANSFER_STATE.PAUSED;
                upload.updatedAt = Date.now();
                this.persistUploads();
                return true;
            }
            return false;
        }

        // 取消上传
        cancelUpload(uploadId) {
            const upload = this.uploads.get(uploadId);
            if (upload) {
                upload.state = TRANSFER_STATE.CANCELLED;
                this.persistUploads();
                
                // 通知服务器取消
                return true;
            }
            return false;
        }

        // 恢复上传
        resumeUpload(uploadId, uploadFn, onProgress) {
            return this.startUpload(uploadId, uploadFn, onProgress);
        }

        // 持久化上传状态
        persistUploads() {
            const data = {};
            for (const [id, upload] of this.uploads) {
                if (upload.state !== TRANSFER_STATE.COMPLETED && 
                    upload.state !== TRANSFER_STATE.CANCELLED) {
                    data[id] = {
                        ...upload,
                        uploadedChunks: Array.from(upload.uploadedChunks),
                        failedChunks: Array.from(upload.failedChunks)
                    };
                }
            }
            localStorage.setItem(this.storageKey, JSON.stringify(data));
        }

        // 加载持久化的上传
        loadPersistedUploads() {
            const data = localStorage.getItem(this.storageKey);
            if (data) {
                try {
                    const parsed = JSON.parse(data);
                    for (const [id, upload] of Object.entries(parsed)) {
                        upload.uploadedChunks = new Set(upload.uploadedChunks);
                        upload.failedChunks = new Set(upload.failedChunks);
                        this.uploads.set(id, upload);
                    }
                } catch (error) {
                    console.error('[ResumableUploadManager] 加载持久化上传失败:', error);
                }
            }
        }

        // 获取上传状态
        getUpload(uploadId) {
            return this.uploads.get(uploadId);
        }

        // 获取所有进行中的上传
        getActiveUploads() {
            return Array.from(this.uploads.values()).filter(
                u => u.state === TRANSFER_STATE.PENDING || 
                     u.state === TRANSFER_STATE.UPLOADING ||
                     u.state === TRANSFER_STATE.PAUSED
            );
        }

        // 通知服务器合并
        async notifyComplete(uploadId, uploadFn) {
            await uploadFn({
                type: 'complete',
                uploadId
            });
        }
    }

    /**
     * 多文件批量传输管理器
     */
    class MultiFileTransferManager {
        constructor(options = {}) {
            this.resumableManager = new ResumableUploadManager(options);
            this.maxConcurrentFiles = options.maxConcurrentFiles || 3;
            this.transfers = new Map();
        }

        // 创建批量传输
        async createBatchTransfer(files, options = {}) {
            const batchId = `batch_${Date.now()}`;
            
            const uploads = [];
            for (const file of files) {
                const uploadId = await this.resumableManager.createUpload(file, options);
                uploads.push(uploadId);
            }

            const batch = {
                id: batchId,
                uploadIds: uploads,
                totalFiles: files.length,
                completedFiles: 0,
                failedFiles: 0,
                state: TRANSFER_STATE.PENDING,
                createdAt: Date.now()
            };

            this.transfers.set(batchId, batch);
            return batchId;
        }

        // 开始批量传输
        async startBatchTransfer(batchId, uploadFn, onProgress = null) {
            const batch = this.transfers.get(batchId);
            if (!batch) throw new Error('Batch not found');

            batch.state = TRANSFER_STATE.UPLOADING;

            const semaphore = new Semaphore(this.maxConcurrentFiles);
            const promises = batch.uploadIds.map(uploadId => 
                semaphore.acquire().then(async () => {
                    try {
                        await this.resumableManager.startUpload(
                            uploadId,
                            uploadFn,
                            (progress) => {
                                if (onProgress) {
                                    onProgress({
                                        batchId,
                                        uploadId,
                                        ...progress
                                    });
                                }
                            }
                        );
                        batch.completedFiles++;
                    } catch (error) {
                        batch.failedFiles++;
                    } finally {
                        semaphore.release();
                    }
                })
            );

            await Promise.all(promises);

            batch.state = batch.failedFiles === 0 ? 
                TRANSFER_STATE.COMPLETED : 
                (batch.completedFiles > 0 ? TRANSFER_STATE.PARTIAL : TRANSFER_STATE.FAILED);

            return batch;
        }

        // 获取批量传输状态
        getBatchStatus(batchId) {
            const batch = this.transfers.get(batchId);
            if (!batch) return null;

            const uploads = batch.uploadIds.map(id => 
                this.resumableManager.getUpload(id)
            );

            return {
                ...batch,
                uploads,
                overallProgress: uploads.reduce((sum, u) => sum + (u?.progress || 0), 0) / uploads.length
            };
        }
    }

    /**
     * 信号量
     */
    class Semaphore {
        constructor(max) {
            this.max = max;
            this.current = 0;
            this.queue = [];
        }

        acquire() {
            return new Promise(resolve => {
                if (this.current < this.max) {
                    this.current++;
                    resolve();
                } else {
                    this.queue.push(resolve);
                }
            });
        }

        release() {
            if (this.queue.length > 0) {
                const next = this.queue.shift();
                next();
            } else {
                this.current--;
            }
        }
    }

    // 辅助函数
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // 导出 - UMD格式
    const exports = {
        CompressionManager,
        EncryptionManager,
        ResumableUploadManager,
        MultiFileTransferManager,
        COMPRESSION_ALGORITHM,
        ENCRYPTION_ALGORITHM,
        TRANSFER_STATE
    };

    if (typeof define === 'function' && define.amd) {
        define([], function() { return exports; });
    } else if (typeof module === 'object' && module.exports) {
        module.exports = exports;
    } else {
        window.Kaelis = window.Kaelis || {};
        window.Kaelis.BinaryTransfer = exports;
        // 保持向后兼容
        window.BinaryTransferAdvanced = exports;
    }

    console.log('[BinaryTransferAdvanced] 高级二进制传输已加载');
})();
