# Plataforma Colaborativa de Preguntas y Respuestas (Q&A) con Asistencia LLM

> **Materia:** Ingeniería de Software I (3385) — Universidad Nacional de Río Cuarto (UNRC)  
> **Estado:** Fase de Planificación y Desarrollo (Misión 2)

---

## Integrantes del Equipo
* **Isaías Cheij**
* **Joaquín**
* **Juan**

---

## Descripción del Proyecto
Plataforma web colaborativa orientada a la comunidad universitaria donde estudiantes y docentes pueden formular preguntas, responder dudas, votar soluciones y contar con un Agente de Respuestas Automáticas impulsado por IA (LLM) para consultas sin responder o identificadas con la etiqueta `#ia-help`.

El diseño del sistema aplica:
* **Principios SOLID** y modularidad.
* **Patrón Factory Method:** para modelar de forma polimórfica la autoría de respuestas (humanos vs. bot de IA).
* **Patrón Strategy:** para integrar múltiples proveedores de LLM (Google Gemini, OpenAI, modelos locales con Ollama) de forma desacoplada.
* **Principios Twelve-Factor / 15-Factor App** para despliegue moderno en la nube.

---

## Gestión y Planificación
La organización de las tareas y el avance del desarrollo se gestionan a través del tablero Kanban en GitHub Projects:

[Ver Tablero del Proyecto en GitHub Projects](../../projects) *(o desde la pestaña Projects de este repositorio)*

---

## Documentación de Diseño y Arquitectura
Los entregables de la etapa de diseño conceptual se encuentran centralizados en el directorio `docs/diseno/`:

* [Informe Técnico y Justificación de Patrones (UML)](docs/diseno/informe_modelo_uml.md)
* [Diagrama de Clases Conceptual (Imagen PNG)](docs/diseno/diagrama_modelo_conceptual.png)
* [Diagrama de Clases en PDF Vectorial](docs/diseno/modeladoUml%20-%20TP.pdf)
* [Archivo Fuente Editable en Draw.io](docs/diseno/modeladoUml%20-%20TP.drawio)

---

## Stack Tecnológico Planificado
* **Lenguaje:** Python 3.12+
* **Gestor de Entorno y Paquetes:** `uv`
* **Framework Web:** Flask (Application Factory + Blueprints)
* **Base de Datos y ORM:** SQLAlchemy (SQLite en desarrollo / PostgreSQL en producción)
* **Migraciones:** Alembic
* **Testing:** PyTest
* **Linter & Formatter:** Ruff