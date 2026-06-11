package com.yourorg.goldensignals.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * FR-02 / AC-03 — IP masking. Test data uses only documentation/TEST-NET ranges
 * (RFC 5737 {@code 192.0.2.0/24}, {@code 203.0.113.0/24}; RFC 3849
 * {@code 2001:db8::/32}) — never real PII (CLAUDE.md §3.1).
 */
class IpMaskingServiceTest {

    private final IpMaskingService masker = new IpMaskingService();

    @Test
    @DisplayName("IPv4 zeroes the last octet")
    void ipv4_zeroesLastOctet() {
        assertThat(masker.mask("203.0.113.42")).isEqualTo("203.0.113.0");
        assertThat(masker.mask("192.0.2.255")).isEqualTo("192.0.2.0");
    }

    @Test
    @DisplayName("IPv6 zeroes the last 80 bits (last 5 hextets)")
    void ipv6_zeroesLast80Bits() {
        // 2001:db8:1:2:3:4:5:6 -> network 2001:0db8:0001 retained, host zeroed.
        final String masked = masker.mask("2001:db8:1:2:3:4:5:6");
        // Java renders the compressed form; assert the host hextets are gone.
        assertThat(masked).startsWith("2001:db8:1:");
        assertThat(masked).doesNotContain(":2:").doesNotContain(":3:").doesNotContain(":6");
        // Re-masking the masked value is idempotent.
        assertThat(masker.mask(masked)).isEqualTo(masked);
    }

    @Test
    @DisplayName("IPv6 compressed form is normalised then masked (E4)")
    void ipv6_compressedFormMasked() {
        final String masked = masker.mask("2001:db8::dead:beef");
        assertThat(masked).startsWith("2001:db8:");
        assertThat(masked).doesNotContain("dead").doesNotContain("beef");
    }

    @Test
    @DisplayName("already-masked IPv4 passes through unchanged (idempotent)")
    void ipv4_idempotent() {
        assertThat(masker.mask("203.0.113.0")).isEqualTo("203.0.113.0");
    }

    @Test
    @DisplayName("malformed / null / hostname inputs never leak raw, return sentinel")
    void malformed_returnsSentinel() {
        assertThat(masker.mask(null)).isEqualTo(IpMaskingService.INVALID);
        assertThat(masker.mask("")).isEqualTo(IpMaskingService.INVALID);
        assertThat(masker.mask("not-an-ip")).isEqualTo(IpMaskingService.INVALID);
        assertThat(masker.mask("evil.example.com")).isEqualTo(IpMaskingService.INVALID);
        assertThat(masker.mask("999.999.999.999")).isEqualTo(IpMaskingService.INVALID);
    }
}
