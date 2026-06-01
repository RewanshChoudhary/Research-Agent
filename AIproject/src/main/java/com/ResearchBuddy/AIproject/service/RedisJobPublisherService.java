package com.ResearchBuddy.AIproject.service;

import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.RedisStreamCommands;
import org.springframework.data.redis.connection.stream.StreamRecords;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;

@RequiredArgsConstructor
@Service
public class RedisJobPublisherService {
    @Value("${app.research.redis.streams.job-stream-name}")
    private String JOB_STREAM;

    private final StringRedisTemplate redis;
    

  

    public void publish(String jobId) {

        redis.opsForStream().add(
                StreamRecords.mapBacked(Map.of("jobId", jobId)).withStreamKey(JOB_STREAM),
                RedisStreamCommands.XAddOptions
                        .maxlen(10000)
                        .approximateTrimming(true));
    }

  

}
