#!/usr/bin/env bash
set -euo pipefail
export FLIGHT_RUNTIME="${FLIGHT_RUNTIME:-/mnt/d/flight-risk-runtime}"
export JAVA_HOME="$FLIGHT_RUNTIME/jre11"
export HADOOP_HOME="$FLIGHT_RUNTIME/hadoop-3.3.6"
export HADOOP_CONF_DIR="$FLIGHT_RUNTIME/conf"
export HADOOP_LOG_DIR="$FLIGHT_RUNTIME/logs/hadoop"
export HADOOP_PID_DIR="$FLIGHT_RUNTIME/pids/hadoop"
export HADOOP_HEAPSIZE_MAX=256
export HADOOP_OPTS="-Djava.net.preferIPv4Stack=true"
export SPARK_HOME="$FLIGHT_RUNTIME/venv/lib/python3.10/site-packages/pyspark"
export SPARK_LOG_DIR="$FLIGHT_RUNTIME/logs/spark"
export SPARK_PID_DIR="$FLIGHT_RUNTIME/pids/spark"
export SPARK_LOCAL_DIRS="$FLIGHT_RUNTIME/spark-tmp"
export SPARK_LOCAL_IP=127.0.0.1
export PYSPARK_PYTHON="$FLIGHT_RUNTIME/venv/bin/python"
export PATH="$JAVA_HOME/bin:$HADOOP_HOME/bin:$FLIGHT_RUNTIME/venv/bin:$PATH"
export HDFS_NAMENODE_USER="$(id -un)"
export HDFS_DATANODE_USER="$(id -un)"
mkdir -p "$HADOOP_CONF_DIR" "$HADOOP_LOG_DIR" "$HADOOP_PID_DIR" "$SPARK_LOG_DIR" "$SPARK_PID_DIR" "$SPARK_LOCAL_DIRS" "$FLIGHT_RUNTIME/spark-events"
