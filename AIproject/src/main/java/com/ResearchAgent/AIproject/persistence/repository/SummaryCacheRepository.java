package com.ResearchAgent.AIproject.persistence.repository;

import com.ResearchAgent.AIproject.persistence.entity.SummaryCacheEntity;
import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SummaryCacheRepository extends JpaRepository<SummaryCacheEntity, UUID> {

    Optional<SummaryCacheEntity> findByUrlHash(String urlHash);

    Optional<SummaryCacheEntity> findByUrlHashAndExpiresAtAfter(String urlHash, LocalDateTime now);

}
