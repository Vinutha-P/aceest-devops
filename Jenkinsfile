// ACEest Fitness & Gym - CI pipeline
// Checkout -> Setup -> Lint -> Unit tests -> SonarQube + Quality Gate
//          -> Docker build -> Tests inside container -> Push to Docker Hub -> Archive
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    // Jenkins polls GitHub every ~2 minutes and builds automatically on new commits
    triggers { pollSCM('H/2 * * * *') }

    // DOCKERHUB_USER is set once as a global environment variable in Jenkins:
    // Manage Jenkins > System > Global properties > Environment variables
    environment {
        IMAGE_REPO = "${env.DOCKERHUB_USER}/aceest-fitness"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    if (!env.DOCKERHUB_USER) {
                        error('DOCKERHUB_USER is not set - add it under Manage Jenkins > System > Global properties')
                    }
                    env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                }
            }
        }

        stage('Setup Python') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements-dev.txt
                '''
                script {
                    env.APP_VERSION = sh(
                        script: '. .venv/bin/activate && python -c "from aceest.version import __version__ as v; print(v)"',
                        returnStdout: true).trim()
                    env.IMAGE_TAG = env.APP_VERSION
                    currentBuild.displayName = "#${env.BUILD_NUMBER} v${env.APP_VERSION} (${env.GIT_SHORT})"
                }
            }
        }

        stage('Lint') {
            steps {
                sh '. .venv/bin/activate && flake8'
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    mkdir -p reports
                    python -m pytest --junitxml=reports/junit.xml \
                        --cov=aceest --cov-report=xml:reports/coverage.xml --cov-report=term
                '''
            }
            post {
                always {
                    junit 'reports/junit.xml'
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'reports/coverage.xml']])
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh 'sonar-scanner -Dsonar.projectVersion=${APP_VERSION}'
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --target runtime \
                        --build-arg APP_VERSION=${APP_VERSION} \
                        -t ${IMAGE_REPO}:${IMAGE_TAG} \
                        -t ${IMAGE_REPO}:${IMAGE_TAG}-b${BUILD_NUMBER} .
                '''
            }
        }

        stage('Test in Container') {
            steps {
                // 1) run the full pytest suite inside the "test" image
                sh '''
                    docker build --target test -t aceest-fitness:test-${BUILD_NUMBER} .
                    docker rm -f aceest-test-${BUILD_NUMBER} 2>/dev/null || true
                    docker create --name aceest-test-${BUILD_NUMBER} aceest-fitness:test-${BUILD_NUMBER}
                    docker start -a aceest-test-${BUILD_NUMBER}
                    docker cp aceest-test-${BUILD_NUMBER}:/app/reports/. reports/
                '''
                // 2) start the real runtime image and smoke-test it
                sh '''
                    docker rm -f aceest-smoke-${BUILD_NUMBER} 2>/dev/null || true
                    docker run -d --name aceest-smoke-${BUILD_NUMBER} ${IMAGE_REPO}:${IMAGE_TAG}
                    for i in $(seq 1 20); do
                        if docker exec aceest-smoke-${BUILD_NUMBER} python -c \
                           "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/version').read().decode())"; then
                            exit 0
                        fi
                        sleep 2
                    done
                    docker logs aceest-smoke-${BUILD_NUMBER}
                    exit 1
                '''
            }
            post {
                always {
                    junit 'reports/junit-container.xml'
                    sh 'docker rm -f aceest-test-${BUILD_NUMBER} aceest-smoke-${BUILD_NUMBER} 2>/dev/null || true'
                }
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub',
                        usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
                    sh '''
                        echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
                        docker push ${IMAGE_REPO}:${IMAGE_TAG}
                        docker push ${IMAGE_REPO}:${IMAGE_TAG}-b${BUILD_NUMBER}
                        docker tag ${IMAGE_REPO}:${IMAGE_TAG} ${IMAGE_REPO}:latest
                        docker push ${IMAGE_REPO}:latest
                    '''
                }
            }
        }

        stage('Archive Artifacts') {
            steps {
                sh '''
                    mkdir -p dist
                    printf '{"app":"aceest-fitness","version":"%s","build":"%s","commit":"%s","image":"%s"}\n' \
                        "${APP_VERSION}" "${BUILD_NUMBER}" "${GIT_SHORT}" "${IMAGE_REPO}:${IMAGE_TAG}" > dist/build-info.json
                    tar czf dist/aceest-fitness-${APP_VERSION}-b${BUILD_NUMBER}.tar.gz \
                        aceest ACEest_Fitness.py requirements.txt Dockerfile dist/build-info.json
                '''
                archiveArtifacts artifacts: 'dist/*, reports/*.xml', fingerprint: true
            }
        }
    }

    post {
        always {
            sh 'docker image rm aceest-fitness:test-${BUILD_NUMBER} 2>/dev/null || true'
        }
        success { echo "Build OK: ${env.IMAGE_REPO}:${env.IMAGE_TAG}" }
        failure { echo 'Build failed - check the stage logs above.' }
    }
}
