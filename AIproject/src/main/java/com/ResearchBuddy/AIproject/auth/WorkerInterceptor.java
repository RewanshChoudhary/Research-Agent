package com.ResearchBuddy.AIproject.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;

// Simple string response instead of ApiError DTO.
// This is an internal endpoint — Python worker parses status codes, not JSON bodies.
@Component
@RequiredArgsConstructor
public class WorkerInterceptor implements HandlerInterceptor {

    @Value("${app.worker.token}")
    private String workerToken;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String token = request.getHeader("X-Worker-Token");
        if (!workerToken.equals(token)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\":\"Invalid worker token\"}");
            return false;
        }
        return true;
    }
}