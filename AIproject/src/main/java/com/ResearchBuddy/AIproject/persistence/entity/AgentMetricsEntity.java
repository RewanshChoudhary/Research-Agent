package com.ResearchBuddy.AIproject.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import java.util.UUID;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
@Entity
@Table(name = "agent_metrics")
public class AgentMetricsEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "job_id", nullable = false)
    private ResearchJobEntity job;

    @Column(name = "agent_name", nullable = false, length = 100)
    private String agentName;

    @Column(name = "started_at", nullable = false)
    private LocalDateTime startedAt;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    @Column(name = "duration_ms")
    private Integer durationMs;

    @Column(name = "llm_calls_made", nullable = false)
    @Builder.Default
    private Integer llmCallsMade = 0;

    @Column(name = "tokens_used", nullable = false)
    @Builder.Default
    private Integer tokensUsed = 0;

    @Column(nullable = false)
    private boolean success;

    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;

    @PrePersist
    void onCreate() {
        if (startedAt == null) {
            startedAt = LocalDateTime.now();
        }
        if (llmCallsMade == null) {
            llmCallsMade = 0;
        }
        if (tokensUsed == null) {
            tokensUsed = 0;
        }
    }
}
