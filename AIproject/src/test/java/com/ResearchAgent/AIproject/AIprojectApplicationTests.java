package com.ResearchAgent.AIproject;

import com.ResearchAgent.AIproject.persistence.repository.UserRepository;
import com.ResearchAgent.AIproject.persistence.repository.ResearchJobRepository;
import com.ResearchAgent.AIproject.persistence.repository.ResearchReportRepository;
import com.ResearchAgent.AIproject.persistence.repository.SourceRepository;
import java.lang.reflect.Proxy;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;

@SpringBootTest(properties = {
		"spring.autoconfigure.exclude=org.springframework.boot.jdbc.autoconfigure.DataSourceAutoConfiguration,"
				+ "org.springframework.boot.hibernate.autoconfigure.HibernateJpaAutoConfiguration,"
				+ "org.springframework.boot.data.jpa.autoconfigure.DataJpaRepositoriesAutoConfiguration",
		"app.research.redis.streams.init-enabled=false" })
@Import(AIprojectApplicationTests.TestConfig.class)
class AIprojectApplicationTests {

	@Test
	void contextLoads() {
	}

	@TestConfiguration(proxyBeanMethods = false)
	static class TestConfig {

		@Bean
		UserRepository userRepository() {
			return repositoryStub(
					UserRepository.class,
					invocation -> {
						if ("findByEmail".equals(invocation.method())) {
							return Optional.empty();
						}
						if ("save".equals(invocation.method())) {
							return invocation.args()[0];
						}
						throw unsupported(invocation.method());
					});
		}

		@Bean
		ResearchJobRepository researchJobRepository() {
			return repositoryStub(
					ResearchJobRepository.class,
					invocation -> {
						throw unsupported(invocation.method());
					});
		}

		@Bean
		ResearchReportRepository researchReportRepository() {
			return repositoryStub(
					ResearchReportRepository.class,
					invocation -> {
						if ("findByJobId".equals(invocation.method())) {
							return Optional.empty();
						}
						throw unsupported(invocation.method());
					});
		}

		@Bean
		SourceRepository sourceRepository() {
			return repositoryStub(
					SourceRepository.class,
					invocation -> {
						if ("findByJobId".equals(invocation.method())) {
							return List.of();
						}
						throw unsupported(invocation.method());
					});
		}

		private static <T> T repositoryStub(Class<T> type, RepositoryCallHandler handler) {
			return type.cast(Proxy.newProxyInstance(
					type.getClassLoader(),
					new Class<?>[] { type },
					(proxy, method, args) -> switch (method.getName()) {
						case "toString" -> type.getSimpleName() + "TestStub";
						case "hashCode" -> System.identityHashCode(proxy);
						case "equals" -> proxy == args[0];
						default -> handler.handle(new RepositoryInvocation(method.getName(), args));
					}));
		}

		private static UnsupportedOperationException unsupported(String methodName) {
			return new UnsupportedOperationException("Unexpected repository method: " + methodName);
		}

		private record RepositoryInvocation(String method, Object[] args) {
		}

		@FunctionalInterface
		private interface RepositoryCallHandler {
			Object handle(RepositoryInvocation invocation) throws Throwable;
		}
	}
}
