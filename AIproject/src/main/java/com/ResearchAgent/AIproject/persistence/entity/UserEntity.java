package com.ResearchAgent.AIproject.persistence.entity;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
@Entity
@Table(name = "users")
public class UserEntity {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @Column(nullable = false, unique = true, length = 255)
  private String email;

  @Column(name = "api_key", nullable = false, unique = true, length = 255)
  private String apiKey;

  @Builder.Default
  @Column(nullable = false, length = 50)
  private String plan = "FREE";

  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;
  @Builder.Default
  @Column(name = "is_active", nullable = false)
  private boolean active = true;

  @OneToMany(mappedBy = "user", fetch = FetchType.LAZY)
  @Builder.Default
  private List<ResearchJobEntity> jobs = new ArrayList<>();

  @OneToMany(mappedBy = "user", fetch = FetchType.LAZY)
  @Builder.Default
  private List<ResearchReportEntity> reports = new ArrayList<>();

  @PrePersist
  void onCreate() {
    if (createdAt == null) {
      createdAt = LocalDateTime.now();
    }
  }
}
