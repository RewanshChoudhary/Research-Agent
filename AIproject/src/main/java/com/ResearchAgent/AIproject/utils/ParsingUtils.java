package com.ResearchAgent.AIproject.utils;

import java.util.List;
import java.util.UUID;

import org.springframework.stereotype.Component;

import tools.jackson.databind.ObjectMapper;

@Component
public class ParsingUtils {
  ObjectMapper objectMapper = new ObjectMapper();
  public UUID parseJobId(String jobId) {
    try {
      return UUID.fromString(jobId);
    } catch (IllegalArgumentException ex) {
      throw new IllegalArgumentException("Invalid job id");
    }
  }

  private String serializeList(List<String> list) {
    if (list == null || list.isEmpty())
      return "[]";
    try {
      return objectMapper.writeValueAsString(list);
    } catch (Exception e) {
      return "[]";
    }
  }
}