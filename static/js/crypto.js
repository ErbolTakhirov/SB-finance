/**
 * ============================================================================
 * КЛИЕНТСКОЕ ШИФРОВАНИЕ - AES-256-GCM через WebCrypto API
 * ============================================================================
 * 
 * ВСЕ данные шифруются на клиенте перед отправкой на сервер.
 * Сервер НИКОГДА не видит расшифрованные данные.
 * 
 * Использование:
 * 1. Генерируйте ключ: await CryptoManager.generateKey()
 * 2. Сохраняйте ключ локально: localStorage.setItem('encryption_key', key)
 * 3. Шифруйте: await crypto.encrypt(data, key)
 * 4. Расшифровывайте: await crypto.decrypt(encrypted, key)
 * ============================================================================
 */

class CryptoManager {
    constructor() {
        this.algorithm = {
            name: 'AES-GCM',
            length: 256,
        };
        this.ivLength = 12; // 96 бит для GCM
    }

    /**
     * Генерирует новый ключ шифрования
     * @returns {Promise<string>} Base64-encoded ключ
     */
    async generateKey() {
        try {
            const key = await crypto.subtle.generateKey(
                this.algorithm,
                true, // extractable
                ['encrypt', 'decrypt']
            );
            
            const exported = await crypto.subtle.exportKey('raw', key);
            return this.arrayBufferToBase64(exported);
        } catch (error) {
            console.error('Ошибка генерации ключа:', error);
            throw new Error('Не удалось сгенерировать ключ шифрования');
        }
    }

    /**
     * Импортирует ключ из Base64 строки
     * @param {string} base64Key - Base64-encoded ключ
     * @returns {Promise<CryptoKey>}
     */
    async importKey(base64Key) {
        try {
            const keyBuffer = this.base64ToArrayBuffer(base64Key);
            return await crypto.subtle.importKey(
                'raw',
                keyBuffer,
                this.algorithm,
                false, // не extractable для безопасности
                ['encrypt', 'decrypt']
            );
        } catch (error) {
            console.error('Ошибка импорта ключа:', error);
            throw new Error('Неверный формат ключа шифрования');
        }
    }

    /**
     * Генерирует случайный IV (Initialization Vector)
     * @returns {Uint8Array}
     */
    generateIV() {
        return crypto.getRandomValues(new Uint8Array(this.ivLength));
    }

    /**
     * Шифрует данные
     * @param {string} plaintext - Текст для шифрования
     * @param {string} base64Key - Base64-encoded ключ
     * @returns {Promise<string>} Base64-encoded зашифрованные данные (IV + ciphertext)
     */
    async encrypt(plaintext, base64Key) {
        try {
            const key = await this.importKey(base64Key);
            const iv = this.generateIV();
            const encoder = new TextEncoder();
            const data = encoder.encode(plaintext);

            const encrypted = await crypto.subtle.encrypt(
                {
                    name: this.algorithm.name,
                    iv: iv,
                },
                key,
                data
            );

            // Объединяем IV и зашифрованные данные
            const combined = new Uint8Array(iv.length + encrypted.byteLength);
            combined.set(iv, 0);
            combined.set(new Uint8Array(encrypted), iv.length);

            return this.arrayBufferToBase64(combined.buffer);
        } catch (error) {
            console.error('Ошибка шифрования:', error);
            throw new Error('Не удалось зашифровать данные');
        }
    }

    /**
     * Расшифровывает данные
     * @param {string} encryptedBase64 - Base64-encoded зашифрованные данные
     * @param {string} base64Key - Base64-encoded ключ
     * @returns {Promise<string>} Расшифрованный текст
     */
    async decrypt(encryptedBase64, base64Key) {
        try {
            const key = await this.importKey(base64Key);
            const combined = this.base64ToArrayBuffer(encryptedBase64);
            const combinedArray = new Uint8Array(combined);

            // Извлекаем IV и зашифрованные данные
            const iv = combinedArray.slice(0, this.ivLength);
            const ciphertext = combinedArray.slice(this.ivLength);

            const decrypted = await crypto.subtle.decrypt(
                {
                    name: this.algorithm.name,
                    iv: iv,
                },
                key,
                ciphertext
            );

            const decoder = new TextDecoder();
            return decoder.decode(decrypted);
        } catch (error) {
            console.error('Ошибка расшифровки:', error);
            throw new Error('Не удалось расшифровать данные. Проверьте ключ.');
        }
    }

    /**
     * Шифрует объект (JSON)
     * @param {Object} obj - Объект для шифрования
     * @param {string} base64Key - Base64-encoded ключ
     * @returns {Promise<string>}
     */
    async encryptObject(obj, base64Key) {
        const json = JSON.stringify(obj);
        return await this.encrypt(json, base64Key);
    }

    /**
     * Расшифровывает объект (JSON)
     * @param {string} encryptedBase64 - Зашифрованные данные
     * @param {string} base64Key - Base64-encoded ключ
     * @returns {Promise<Object>}
     */
    async decryptObject(encryptedBase64, base64Key) {
        const json = await this.decrypt(encryptedBase64, base64Key);
        return JSON.parse(json);
    }

    /**
     * Генерирует seed phrase (12 слов) для восстановления ключа
     * @returns {string}
     */
    generateSeedPhrase() {
        // Простой генератор seed phrase (в продакшене используйте BIP39 библиотеку)
        const words = [
            'абрикос', 'банан', 'вишня', 'груша', 'дыня', 'ежевика', 'жёлудь', 'земляника',
            'инжир', 'йогурт', 'каштан', 'лимон', 'манго', 'нектарин', 'орех', 'персик',
            'рябина', 'слива', 'тыква', 'урюк', 'финик', 'хурма', 'черешня', 'яблоко',
            'апельсин', 'брусника', 'виноград', 'грейпфрут', 'дыня', 'ежевика', 'жимолость', 'земляника'
        ];
        
        const selected = [];
        for (let i = 0; i < 12; i++) {
            selected.push(words[Math.floor(Math.random() * words.length)]);
        }
        return selected.join(' ');
    }

    /**
     * Генерирует ключ из seed phrase
     * @param {string} seedPhrase - Seed phrase
     * @returns {Promise<string>}
     */
    async deriveKeyFromSeed(seedPhrase) {
        const encoder = new TextEncoder();
        const data = encoder.encode(seedPhrase);
        
        // Используем PBKDF2 для получения ключа из seed
        const keyMaterial = await crypto.subtle.importKey(
            'raw',
            data,
            'PBKDF2',
            false,
            ['deriveBits']
        );

        const derivedBits = await crypto.subtle.deriveBits(
            {
                name: 'PBKDF2',
                salt: encoder.encode('sb_finance_salt_2024'), // В продакшене используйте уникальную соль
                iterations: 100000, // Высокая сложность для безопасности
                hash: 'SHA-256',
            },
            keyMaterial,
            256 // 256 бит = 32 байта
        );

        return this.arrayBufferToBase64(derivedBits);
    }

    /**
     * Конвертирует ArrayBuffer в Base64
     * @param {ArrayBuffer} buffer
     * @returns {string}
     */
    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    /**
     * Конвертирует Base64 в ArrayBuffer
     * @param {string} base64
     * @returns {ArrayBuffer}
     */
    base64ToArrayBuffer(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    /**
     * Проверяет, поддерживается ли WebCrypto API
     * @returns {boolean}
     */
    static isSupported() {
        return typeof crypto !== 'undefined' && 
               crypto.subtle !== undefined &&
               typeof crypto.subtle.encrypt === 'function';
    }
}

// Глобальный экземпляр
const cryptoManager = new CryptoManager();

// ============================================================================
// УТИЛИТЫ ДЛЯ РАБОТЫ С КЛЮЧАМИ В LOCALSTORAGE
// ============================================================================

const EncryptionStorage = {
    /**
     * Получает или создаёт ключ шифрования
     * @returns {Promise<string>}
     */
    async getOrCreateKey() {
        let key = localStorage.getItem('encryption_key');
        if (!key) {
            key = await cryptoManager.generateKey();
            localStorage.setItem('encryption_key', key);
        }
        return key;
    },

    /**
     * Сохраняет ключ
     * @param {string} key
     */
    saveKey(key) {
        localStorage.setItem('encryption_key', key);
    },

    /**
     * Удаляет ключ
     */
    clearKey() {
        localStorage.removeItem('encryption_key');
        localStorage.removeItem('seed_phrase');
    },

    /**
     * Сохраняет seed phrase
     * @param {string} seedPhrase
     */
    saveSeedPhrase(seedPhrase) {
        localStorage.setItem('seed_phrase', seedPhrase);
    },

    /**
     * Получает seed phrase
     * @returns {string|null}
     */
    getSeedPhrase() {
        return localStorage.getItem('seed_phrase');
    },

    /**
     * Проверяет наличие ключа
     * @returns {boolean}
     */
    hasKey() {
        return localStorage.getItem('encryption_key') !== null;
    }
};

// ============================================================================
// АВТОМАТИЧЕСКОЕ ШИФРОВАНИЕ ДЛЯ API
// ============================================================================

/**
 * Перехватывает fetch запросы и автоматически шифрует данные
 */
class EncryptedFetch {
    constructor() {
        this.encryptionEnabled = true;
    }

    /**
     * Включает/выключает шифрование
     * @param {boolean} enabled
     */
    setEnabled(enabled) {
        this.encryptionEnabled = enabled;
    }

    /**
     * Обёртка над fetch с автоматическим шифрованием
     * @param {string} url
     * @param {Object} options
     * @returns {Promise<Response>}
     */
    async fetch(url, options = {}) {
        if (!this.encryptionEnabled) {
            return fetch(url, options);
        }

        const key = await EncryptionStorage.getOrCreateKey();
        const originalBody = options.body;

        // Шифруем body если это JSON
        if (originalBody && typeof originalBody === 'string') {
            try {
                const json = JSON.parse(originalBody);
                const encrypted = await cryptoManager.encryptObject(json, key);
                options.body = JSON.stringify({
                    encrypted: true,
                    data: encrypted
                });
                if (!options.headers) options.headers = {};
                options.headers['Content-Type'] = 'application/json';
            } catch (e) {
                // Если не JSON, шифруем как текст
                const encrypted = await cryptoManager.encrypt(originalBody, key);
                options.body = JSON.stringify({
                    encrypted: true,
                    data: encrypted
                });
                if (!options.headers) options.headers = {};
                options.headers['Content-Type'] = 'application/json';
            }
        }

        const response = await fetch(url, options);

        // Расшифровываем ответ если он зашифрован
        if (response.headers.get('content-type')?.includes('application/json')) {
            const data = await response.json();
            if (data.encrypted && data.data) {
                const decrypted = await cryptoManager.decryptObject(data.data, key);
                return new Response(JSON.stringify(decrypted), {
                    status: response.status,
                    statusText: response.statusText,
                    headers: response.headers
                });
            }
        }

        return response;
    }
}

// Глобальный экземпляр для автоматического шифрования
const encryptedFetch = new EncryptedFetch();

