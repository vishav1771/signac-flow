{% extends "base_script.sh" %}
{% block header %}
#PBS -N {{ id }}
{% if walltime is not none %}
#PBS -l walltime={{ walltime|format_timedelta }}
{% endif %}
{% if not no_copy_env %}
#PBS -V
{% endif %}
{% block tasks %}
{% set s_ppn = ':ppn=' ~ ppn if ppn else '' %}
{% set nn = (num_tasks/ppn)|round(method='ceil')|int if ppn else num_tasks %}
#PBS -l nodes={{ nn }}{{ s_ppn }}
{% endif %}
{% endblock %}
{% endblock %}
