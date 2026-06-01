package com.ResearchBuddy.AIproject.service;

import com.ResearchBuddy.AIproject.persistence.entity.UserEntity;
import com.ResearchBuddy.AIproject.persistence.repository.UserRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class LocalUserService {

  private static final String LOCAL_USER_EMAIL = "local@researchbuddy.dev";
  private static final String LOCAL_USER_API_KEY = "local-only";

  private final UserRepository userRepository;

  @Transactional
  public UserEntity getOrCreateLocalUser() {
    return userRepository.findByEmail(LOCAL_USER_EMAIL)
        .orElseGet(() -> userRepository.save(UserEntity.builder()
            .email(LOCAL_USER_EMAIL)
            .apiKey(LOCAL_USER_API_KEY)
            .plan("FREE")
            .active(true)
            .build()));
  }
}
