# Jenkins controller with everything the ACEest pipeline needs:
#   python3      -> virtualenv, flake8, pytest
#   docker CLI   -> builds/pushes images using the host Docker (socket mount)
#   kubectl      -> deploys to Minikube / Kubernetes
#   sonar-scanner-> SonarQube static analysis
FROM jenkins/jenkins:lts-jdk21

USER root
ARG KUBECTL_VERSION=v1.31.4
ARG SONAR_SCANNER_VERSION=6.2.1.4610

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv python3-pip curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI only - the daemon is Docker Desktop on the host
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker

# kubectl
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSLo /usr/local/bin/kubectl \
       "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" \
    && chmod +x /usr/local/bin/kubectl

# sonar-scanner (platform independent build, runs on the bundled JDK 21)
RUN curl -fsSLo /tmp/sonar.zip \
      "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VERSION}.zip" \
    && unzip -q /tmp/sonar.zip -d /opt \
    && ln -s "/opt/sonar-scanner-${SONAR_SCANNER_VERSION}/bin/sonar-scanner" /usr/local/bin/sonar-scanner \
    && rm /tmp/sonar.zip

USER jenkins
COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
