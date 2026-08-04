package com.ResearchAgent.AIproject.controller;

import com.ResearchAgent.AIproject.persistence.dto.WorkerCompleteRequest;
import com.ResearchAgent.AIproject.persistence.dto.WorkerFailRequest;
import com.ResearchAgent.AIproject.persistence.dto.WorkerJobDetailsResponse;
import com.ResearchAgent.AIproject.persistence.dto.WorkerStatusUpdateRequest;
import com.ResearchAgent.AIproject.service.WorkerJobService;
import jakarta.validation.Valid;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// Thin controller — zero business logic. All delegation to WorkerJobService.
// @Valid on request body ensures Python sends correct payload shape.
// UUID path binding avoids manual parsing from String.
@RestController
@RequestMapping("/internal/worker")
@RequiredArgsConstructor
public class WorkerJobController {

    private final WorkerJobService workerJobService;

    @GetMapping("/jobs/{jobId}")
    public ResponseEntity<WorkerJobDetailsResponse> getJobDetails(@PathVariable UUID jobId) {
        return ResponseEntity.ok(workerJobService.getJobDetails(jobId));
    }

    @PatchMapping("/jobs/{jobId}/status")
    public ResponseEntity<Void> updateStatus(
            @PathVariable UUID jobId,
            @Valid @RequestBody WorkerStatusUpdateRequest body) {
        workerJobService.updateStatus(jobId, body);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/jobs/{jobId}/complete")
    public ResponseEntity<Void> completeJob(
            @PathVariable UUID jobId,
            @Valid @RequestBody WorkerCompleteRequest body) {
        workerJobService.completeJob(jobId, body);
        return ResponseEntity.ok().build();
    }

    @PostMapping("/jobs/{jobId}/fail")
    public ResponseEntity<Void> failJob(
            @PathVariable UUID jobId,
            @Valid @RequestBody WorkerFailRequest body) {
        workerJobService.failJob(jobId, body);
        return ResponseEntity.ok().build();
    }
}
