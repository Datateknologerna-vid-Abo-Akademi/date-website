{{/*
Expand the name of the chart.
*/}}
{{- define "date-website.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "date-website.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "date-website.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "date-website.labels" -}}
helm.sh/chart: {{ include "date-website.chart" . }}
app.kubernetes.io/name: {{ include "date-website.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "date-website.selectorLabels" -}}
app.kubernetes.io/name: {{ include "date-website.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "date-website.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "date-website.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "date-website.secretName" -}}
{{- default (include "date-website.fullname" .) .Values.secret.existingSecret }}
{{- end }}

{{- define "date-website.postgresql.fullname" -}}
{{- printf "%s-postgresql" (include "date-website.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "date-website.redis.fullname" -}}
{{- printf "%s-redis" (include "date-website.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "date-website.backupsPvcName" -}}
{{- printf "%s-postgresql-backups" (include "date-website.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "date-website.dbHost" -}}
{{- if .Values.postgresql.enabled }}
{{- include "date-website.postgresql.fullname" . }}
{{- else }}
{{- required "database.external.host is required when postgresql.enabled=false" .Values.database.external.host }}
{{- end }}
{{- end }}

{{- define "date-website.dbPort" -}}
{{- if .Values.postgresql.enabled }}5432{{ else }}{{ .Values.database.external.port }}{{ end }}
{{- end }}

{{- define "date-website.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s:6379" (include "date-website.redis.fullname" .) }}
{{- else }}
{{- required "redis.externalUrl is required when redis.enabled=false" .Values.redis.externalUrl }}
{{- end }}
{{- end }}

{{- define "date-website.probeHost" -}}
{{- $allowedHosts := .Values.django.allowedHosts | default list -}}
{{- if gt (len $allowedHosts) 0 -}}
{{- first $allowedHosts -}}
{{- else -}}
{{- fail "django.allowedHosts must contain at least one host for Kubernetes probes" -}}
{{- end }}
{{- end }}

{{- define "date-website.mediaVolume" -}}
{{- if and .Values.media.persistence.enabled (not .Values.media.s3.enabled) }}
volumes:
  - name: media
    persistentVolumeClaim:
      claimName: {{ include "date-website.fullname" . }}-media
{{- end }}
{{- end }}

{{- define "date-website.mediaVolumeMount" -}}
{{- if and .Values.media.persistence.enabled (not .Values.media.s3.enabled) }}
volumeMounts:
  - name: media
    mountPath: /code/media
{{- end }}
{{- end }}
