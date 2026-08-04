package com.ResearchAgent.AIproject.config;

import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.ReadOffset;
import org.springframework.data.redis.core.StringRedisTemplate;

import lombok.RequiredArgsConstructor;

@Configuration
@RequiredArgsConstructor
public class RedisStreamsConfig {
  @Value("${app.research.redis.streams.job-stream-name}")
  private String JOB_STREAM;
  @Value("${app.research.redis.streams.job-consumer-group}")
  private String JOB_GROUP;
  @Value("${app.research.redis.streams.dead-letter-stream-name}")
  private String JOB_DLQ_STREAM;

  @Bean
  @ConditionalOnProperty(name = "app.research.redis.streams.init-enabled", havingValue = "true", matchIfMissing = true)
  ApplicationRunner initStreamsConfig(StringRedisTemplate redis) {
    return args -> {
      if (!Boolean.TRUE.equals(redis.hasKey(JOB_STREAM))) {
        redis.opsForStream().add(MapRecord.create(JOB_STREAM, Map.of("start", "1")));
      }

      try {
        redis.opsForStream().createGroup(JOB_STREAM, ReadOffset.latest(), JOB_GROUP);

      } catch (Exception e) {
        if (!hasMessage(e, "BUSYGROUP")) {
          throw e;
        }

      }
    };

  }

  private boolean hasMessage(Throwable throwable, String expectedText) {
    Throwable current = throwable;
    while (current != null) {
      String message = current.getMessage();
      if (message != null && message.contains(expectedText)) {
        return true;
      }
      current = current.getCause();
    }
    return false;
  }
}
