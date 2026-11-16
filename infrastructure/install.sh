#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT/infrastructure/runtime.sh"
test -f "$FLIGHT_RUNTIME/downloads.json" || { echo 'Run scripts/bootstrap_downloads.py first'; exit 1; }
if [ ! -x "$JAVA_HOME/bin/java" ]; then
  mkdir -p "$JAVA_HOME"
  tar -xzf "$FLIGHT_RUNTIME/jre11.tar.gz" -C "$JAVA_HOME" --strip-components=1
fi
if [ ! -f "$HADOOP_HOME/.flight-install-complete" ]; then
  # Omit bundled HTML documentation: NTFS small-file extraction is expensive.
  # All executables, configuration and runtime jars are retained.
  tar -xzf "$FLIGHT_RUNTIME/hadoop-3.3.6.tar.gz" --exclude='hadoop-3.3.6/share/doc' -C "$FLIGHT_RUNTIME"
  touch "$HADOOP_HOME/.flight-install-complete"
fi
cp "$HADOOP_HOME/etc/hadoop/log4j.properties" "$HADOOP_CONF_DIR/log4j.properties"
cat > "$HADOOP_CONF_DIR/core-site.xml" <<EOF
<configuration>
<property><name>fs.defaultFS</name><value>hdfs://127.0.0.1:19000</value></property>
<property><name>hadoop.tmp.dir</name><value>$FLIGHT_RUNTIME/hadoop-tmp</value></property>
</configuration>
EOF
cat > "$HADOOP_CONF_DIR/hdfs-site.xml" <<EOF
<configuration>
<property><name>dfs.replication</name><value>1</value></property>
<property><name>dfs.namenode.name.dir</name><value>file://$FLIGHT_RUNTIME/hdfs/name</value></property>
<property><name>dfs.datanode.data.dir</name><value>file://$FLIGHT_RUNTIME/hdfs/data</value></property>
<property><name>dfs.namenode.http-address</name><value>127.0.0.1:19870</value></property>
<property><name>dfs.datanode.http.address</name><value>127.0.0.1:19864</value></property>
<property><name>dfs.datanode.address</name><value>127.0.0.1:19866</value></property>
<property><name>dfs.datanode.ipc.address</name><value>127.0.0.1:19867</value></property>
<property><name>dfs.namenode.safemode.min.datanodes</name><value>1</value></property>
</configuration>
EOF
printf 'export JAVA_HOME="%s"\n' "$JAVA_HOME" > "$HADOOP_CONF_DIR/hadoop-env.sh"
# Formatting is restricted to a fresh project-specific metadata directory.
if [ ! -f "$FLIGHT_RUNTIME/hdfs/name/current/VERSION" ]; then
  if [ -d "$FLIGHT_RUNTIME/hdfs/name" ] && [ -n "$(ls -A "$FLIGHT_RUNTIME/hdfs/name")" ]; then
    echo 'Existing metadata without VERSION; refusing automatic format'; exit 1
  fi
  hdfs namenode -format -nonInteractive flight-risk
fi
java -version
hdfs version
