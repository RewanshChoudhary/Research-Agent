package com.ResearchBuddy.AIproject.persistence.repository;

import com.ResearchBuddy.AIproject.persistence.entity.ResearchJobEntity;
import com.ResearchBuddy.AIproject.persistence.entity.enums.JobStatus;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ResearchJobRepository extends JpaRepository<ResearchJobEntity, UUID> {

  List<ResearchJobEntity> findByUserIdOrderByCreatedAtDesc(UUID userId);

  List<ResearchJobEntity> findByStatus(JobStatus status);
}
