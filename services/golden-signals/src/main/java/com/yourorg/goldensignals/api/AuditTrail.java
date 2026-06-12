package com.yourorg.goldensignals.api;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Append-only in-memory audit trail (FR-14, ADR-0026). Every authenticated
 * request records {@code (ts, endpoint, hashed_key, trace_id, status)}. The API
 * key is never stored in clear — only its SHA-256 hex digest (CLAUDE.md §3.1/§3.2).
 * The list is bounded to {@code AUDIT_MAX_ENTRIES} (oldest dropped) to bound memory.
 *
 * <p>This is the in-memory initial scope; a durable immutable sink (ADR-0026
 * audit_logger) is the production target recorded in a later phase.
 */
@Component
public class AuditTrail {

    /** One immutable audit record (FR-14). */
    public record Entry(String ts, String endpoint, String hashedKey, String traceId, int status) {
    }

    private final int maxEntries;
    private final List<Entry> entries = new ArrayList<>();
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    public AuditTrail(@Value("${gs.audit-max-entries:10000}") final int maxEntries) {
        this.maxEntries = maxEntries;
    }

    /**
     * Append one audit record.
     *
     * @param endpoint the request endpoint (e.g. {@code POST /ingestion})
     * @param apiKey   the raw API key (hashed before storage; may be null)
     * @param traceId  the request trace id (NFR-03)
     * @param status   the HTTP status returned
     */
    public void record(final String endpoint, final String apiKey, final String traceId,
                       final int status) {
        final Entry entry = new Entry(
                Instant.now().toString(), endpoint, hash(apiKey), traceId, status);
        lock.writeLock().lock();
        try {
            entries.add(entry);
            if (entries.size() > maxEntries) {
                entries.remove(0);
            }
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * The most recent {@code limit} entries, newest last.
     *
     * @param limit max entries to return (clamped to the stored count)
     * @return an immutable snapshot
     */
    public List<Entry> recent(final int limit) {
        lock.readLock().lock();
        try {
            final int from = Math.max(0, entries.size() - Math.max(0, limit));
            return Collections.unmodifiableList(new ArrayList<>(entries.subList(from, entries.size())));
        } finally {
            lock.readLock().unlock();
        }
    }

    private static String hash(final String apiKey) {
        if (apiKey == null || apiKey.isEmpty()) {
            return "anonymous";
        }
        try {
            final MessageDigest md = MessageDigest.getInstance("SHA-256");
            final byte[] digest = md.digest(apiKey.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (final NoSuchAlgorithmException ex) {
            // SHA-256 is guaranteed present on every JVM; treat as fatal config error.
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
