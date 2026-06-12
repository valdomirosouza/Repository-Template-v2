package com.yourorg.goldensignals.domain;

import java.net.InetAddress;
import java.net.UnknownHostException;
import org.springframework.stereotype.Component;

/**
 * Masks client IPs before any persist or log write (FR-02, ADR-0012, CLAUDE.md §3.1).
 *
 * <ul>
 *   <li>IPv4 → last octet zeroed (e.g. {@code 203.0.113.42 → 203.0.113.0}).</li>
 *   <li>IPv6 → last 80 bits (last 10 bytes / last 5 hextets) zeroed
 *       (e.g. {@code 2001:db8:1:2:3:4:5:6 → 2001:db8:1:0:0:0:0:0}).</li>
 * </ul>
 *
 * <p>Pure and idempotent: masking an already-masked address is a no-op. A
 * malformed address is replaced with a safe sentinel ({@code "invalid"}) and is
 * never persisted or logged in raw form (FR-02, AC-03). The service uses only
 * {@code getByName} on a literal numeric address (no DNS lookup), so it performs
 * no network I/O.
 */
@Component
public class IpMaskingService {

    /** Returned for an unparseable input so no raw value ever leaks. */
    public static final String INVALID = "invalid";

    private static final int IPV4_BYTES = 4;
    private static final int IPV6_BYTES = 16;
    private static final int IPV6_HOST_BYTES = 10; // last 80 bits

    /**
     * Mask an IP literal. Accepts IPv4 dotted-quad or IPv6 (including compressed
     * {@code ::} forms); the address is normalised by parsing before masking (E4).
     *
     * @param ip the raw IP literal (numeric; not a hostname)
     * @return the masked address, or {@link #INVALID} if unparseable
     */
    public String mask(final String ip) {
        if (ip == null || ip.isBlank()) {
            return INVALID;
        }
        final String candidate = ip.trim();
        // Reject hostnames outright: a numeric literal contains only IP chars.
        if (!isNumericLiteral(candidate)) {
            return INVALID;
        }
        final byte[] addr;
        try {
            addr = InetAddress.getByName(candidate).getAddress();
        } catch (final UnknownHostException ex) {
            return INVALID;
        }
        if (addr.length == IPV4_BYTES) {
            addr[IPV4_BYTES - 1] = 0;
        } else if (addr.length == IPV6_BYTES) {
            for (int i = IPV6_BYTES - IPV6_HOST_BYTES; i < IPV6_BYTES; i++) {
                addr[i] = 0;
            }
        } else {
            return INVALID;
        }
        try {
            return InetAddress.getByAddress(addr).getHostAddress();
        } catch (final UnknownHostException ex) {
            return INVALID;
        }
    }

    private static boolean isNumericLiteral(final String s) {
        for (int i = 0; i < s.length(); i++) {
            final char c = s.charAt(i);
            final boolean ok = (c >= '0' && c <= '9')
                    || (c >= 'a' && c <= 'f')
                    || (c >= 'A' && c <= 'F')
                    || c == '.' || c == ':' || c == '%';
            if (!ok) {
                return false;
            }
        }
        return true;
    }
}
