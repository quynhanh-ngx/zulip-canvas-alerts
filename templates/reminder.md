Hello, you are receiving this message because you 
have unsubmitted assignments that are overdue.

{#{% if upcoming_assignments %}#}
{### Upcoming assignments#}
{#{% for x in upcoming_assignments -%}#}
{#- **[{{x.name}}]({{x.url}}): {{ x.due_date }}** *({{ x.days_remaining }} days remaining)*#}
{#{% endfor %}#}
{#{% endif %}#}

{% if overdue_assignments %}
## Overdue assignments
{% for x in overdue_assignments -%}
- **[{{x.name}}]({{x.url}}): {{ x.due_date }}** *({{ x.days_remaining|abs }} days overdue)* {% if x.solution %}([{{x.solution.text}}]({{ x.solution.link }})){% endif %}
{% endfor %}
{% endif %}

{% if resources %}

{# Office hours, link to lecture videos, etc #}
## Resources
{% for resource in resources %}

{% if resource.link %}
- [{{ resource.text }}]({{ resource.link }})
{%- else %}
- {{ resource.text }}
{%- endif %}
{%- endfor %}
{%- endif %}
