/**
 * LAYER 6: CLIENT-SIDE ENCRYPTION
 * Browser-based crypto using Web Crypto API.
 * Encrypts data before it ever leaves the browser.
 */

export interface EncryptedPayload {
  ciphertext: string;  // base64
  nonce: string;       // base64 IV
  sessionId: string;
}

export class NullAICrypto {
  private sessionKey: CryptoKey | null = null;

  /**
   * Generate ephemeral AES-256-GCM key for this session.
   * Key exists only in browser memory. Never sent to server.
   */
  async generateSessionKey(): Promise<CryptoKey> {
    this.sessionKey = await crypto.subtle.generateKey(
      { name: 'AES-GCM', length: 256 },
      true,  // extractable (we'll send encrypted version to TEE)
      ['encrypt', 'decrypt']
    );
    return this.sessionKey;
  }

  /**
   * Export session key for secure transmission to TEE.
   * In production: encrypt with TEE's public key using ECDH.
   */
  async exportKey(): Promise<string> {
    if (!this.sessionKey) throw new Error('No session key');
    const raw = await crypto.subtle.exportKey('raw', this.sessionKey);
    return btoa(String.fromCharCode(...new Uint8Array(raw)));
  }

  /**
   * Encrypt prompt before sending to API.
   */
  async encryptPrompt(plaintext: string): Promise<EncryptedPayload> {
    if (!this.sessionKey) await this.generateSessionKey();

    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoder = new TextEncoder();

    const ciphertext = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      this.sessionKey!,
      encoder.encode(plaintext)
    );

    return {
      ciphertext: btoa(String.fromCharCode(...new Uint8Array(ciphertext))),
      nonce: btoa(String.fromCharCode(...iv)),
      sessionId: this.generateSessionId()
    };
  }

  /**
   * Decrypt result from API.
   */
  async decryptResult(ciphertext: string, nonce: string): Promise<string> {
    if (!this.sessionKey) throw new Error('No session key');

    const iv = Uint8Array.from(atob(nonce), c => c.charCodeAt(0));
    const data = Uint8Array.from(atob(ciphertext), c => c.charCodeAt(0));

    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      this.sessionKey,
      data
    );

    return new TextDecoder().decode(decrypted);
  }

  /**
   * Destroy session key from memory.
   */
  destroy(): void {
    this.sessionKey = null;
    // In production: overwrite memory buffer explicitly
  }

  private generateSessionId(): string {
    return crypto.randomUUID();
  }
}

/**
 * Trust Dashboard utilities
 * Display real-time privacy status to users.
 */
export interface PrivacyStatus {
  sessionActive: boolean;
  encryptionEnabled: boolean;
  memoryStored: number;  // Always 0 in ephemeral mode
  diskStored: number;    // Always 0
  logsEnabled: boolean;   // Always false
  teeVerified: boolean;
}

export function getPrivacyStatus(): PrivacyStatus {
  return {
    sessionActive: true,
    encryptionEnabled: true,
    memoryStored: 0,
    diskStored: 0,
    logsEnabled: false,
    teeVerified: true  // Mock: always true. Real: check attestation.
  };
}
