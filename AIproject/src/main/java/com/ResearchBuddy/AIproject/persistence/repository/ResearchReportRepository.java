package com.ResearchBuddy.AIproject.persistence.repository;

import com.ResearchBuddy.AIproject.persistence.entity.ResearchReportEntity;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ResearchReportRepository extends JpaRepository<ResearchReportEntity, UUID> {

    List<ResearchReportEntity> findByUserIdOrderByCreatedAtDesc(UUID userId);

    Optional<ResearchReportEntity> findByJobId(UUID jobId);
}
