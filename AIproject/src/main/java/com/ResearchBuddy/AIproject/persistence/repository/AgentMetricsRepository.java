package com.ResearchBuddy.AIproject.persistence.repository;

import com.ResearchBuddy.AIproject.persistence.entity.AgentMetricsEntity;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentMetricsRepository extends JpaRepository<AgentMetricsEntity, UUID> {

    List<AgentMetricsEntity> findByJobIdOrderByStartedAtAsc(UUID jobId);
}
