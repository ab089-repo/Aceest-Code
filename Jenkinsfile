pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timeout(time: 15, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        // Jenkins runs locally and cannot receive GitHub webhooks, so poll for new commits
        pollSCM('H/5 * * * *')
    }

    environment {
        VENV = "${WORKSPACE}/.venv"
    }

    stages {
        stage('Checkout') {
            steps {
                // Start from an empty workspace so every build is a clean build
                deleteDir()
                checkout scm
            }
        }

        stage('Build Environment') {
            steps {
                sh '''
                    python3 --version
                    python3 -m venv "$VENV"
                    "$VENV/bin/pip" install --no-cache-dir --disable-pip-version-check -r requirements-dev.txt
                '''
            }
        }

        stage('Compile') {
            steps {
                sh '"$VENV/bin/python" -m compileall -q app.py tests'
            }
        }

        stage('Lint') {
            steps {
                sh '"$VENV/bin/flake8"'
            }
        }

        stage('Unit Tests') {
            steps {
                sh '"$VENV/bin/pytest" --junitxml=reports/junit.xml --cov=app --cov-report=term-missing'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                }
            }
        }
    }

    post {
        success {
            echo 'Quality gate passed: the code compiles, lints cleanly and all tests pass.'
        }
        failure {
            echo 'Quality gate failed: see the stage logs above.'
        }
    }
}
