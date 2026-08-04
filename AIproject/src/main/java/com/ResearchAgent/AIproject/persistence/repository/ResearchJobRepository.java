package com.ResearchAgent.AIproject.persistence.repository;

import com.ResearchAgent.AIproject.persistence.entity.ResearchJobEntity;
import com.ResearchAgent.AIproject.persistence.entity.enums.JobStatus;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ResearchJobRepository extends JpaRepository<ResearchJobEntity, UUID> {

  List<ResearchJobEntity> findByUserIdOrderByCreatedAtDesc(UUID userId);

  List<ResearchJobEntity> findByStatus(JobStatus status);
}
