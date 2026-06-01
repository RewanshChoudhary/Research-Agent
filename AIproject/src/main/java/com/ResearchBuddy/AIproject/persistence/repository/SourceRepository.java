package com.ResearchBuddy.AIproject.persistence.repository;

import com.ResearchBuddy.AIproject.persistence.entity.SourceEntity;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SourceRepository extends JpaRepository<SourceEntity, UUID> {

    List<SourceEntity> findByJobId(UUID jobId);
}
