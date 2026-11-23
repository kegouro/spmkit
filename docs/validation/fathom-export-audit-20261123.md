# Revisión de análisis y exportación de Fathom

Revisión local del 23 de noviembre de 2026 sobre la rama de interfaz. Se inspeccionaron el visor de fuerza, los controles, el mapa, los comandos de exportación y los informes. Las pruebas usan curvas sintéticas con propiedades conocidas y el pipeline como referencia.

## Correcciones verificadas

| Problema reproducible | Corrección y evidencia |
| --- | --- |
| Exportar todo e informar reconstruían un ajuste con solo modelo, radio y Poisson. Se perdían calibración manual, suavizado, ventana y opciones de contacto. | Ambos reciben la receta activa capturada al iniciar la tarea. El informe usa esa misma receta para la curva representativa. Una prueba compara los módulos exportados con el pipeline bajo radio y ventana modificados. |
| Un cambio de receta dejaba resultados anteriores visibles durante el nuevo cálculo. | Se emite inmediatamente el estado válido o vacío, se retiran ajuste y residuos anteriores y se vuelve a dibujar la adquisición disponible. |
| Los controles conservaban valores anteriores al restaurar parámetros de un proyecto. Una edición posterior podía reenviar esos valores. | Se sincronizan con el estado del análisis y se bloquea la aplicación durante la actualización. La prueba cambia radio y suavizado externamente y luego edita Poisson desde el panel. |
| Un mapa calculado con una receta anterior seguía disponible. Una tarea en segundo plano podía restaurarlo tras cambiar receta o adquisición. | Se invalida por receta y adquisición, se captura la configuración al iniciar y se descartan resultados de generaciones anteriores. Se prueba la finalización tardía. |
| El CSV etiquetaba como separación la altura utilizada como sustitución. | El exportador comparte la selección del eje con el ajuste y escribe height o separation según corresponda. La prueba incluye separación degenerada. |
| El JSON podía emitir NaN y carecía de receta y unidades. Un error de escritura escapaba del comando de UI. | Los valores no finitos se representan con null. Se incluyen receta, índice, origen, hash disponible y unidades. Los fallos se muestran en la barra de estado. |

Los informes y la exportación integral guardan además la receta y las unidades en un JSON de análisis. La fuente del informe corresponde al archivo cargado. Las pruebas están en tests/gui/test_export_audit.py, tests/core/test_forcereport.py y tests/core/test_export_volume.py.

## Pendientes relevantes para datos reales

- **Exactitud de módulos JPK.** Sigue abierta la validación del eje físico descrita en el contraste PAAm. Se observó una dependencia grande del canal de altura usado. Para publicar módulos absolutos hace falta contrastar la posición de punta con el instrumento y fijar el protocolo. [Resultados públicos](force-steps-public/README.md)
- **Escalones en la UI.** La CLI force-steps admite anotaciones reproducibles y su sensibilidad. El visor interactivo actual mide diferencias entre puntos. Hace falta integrar la anotación de fronteras y las dos regresiones del método de escalones en la interfaz para repetirlo desde Fathom.
- **JKR experimental.** Su operación toma una ruta propia que utiliza radio, Poisson y umbral. El cálculo ahora rechaza explícitamente ventana manual y Monte Carlo para evitar omitirlos silenciosamente. Implementar esas opciones para JKR queda pendiente.
- **Exportaciones interrumpidas.** La exportación integral escribe varios archivos secuencialmente. Puede quedar una carpeta parcial si falla una escritura o el informe. La recuperación y reanudación del lote siguen previstas en el plan.
- **Entornos de distribución.** Esta revisión se ejecutó en macOS/Python 3.12. La matriz remota de plataformas requiere verificación sobre la revisión candidata a distribución.

La coincidencia entre la exportación y el pipeline verifica consistencia del programa. La validación experimental de las liquid marbles necesita originales, calibraciones y controles de adquisición.

## Verificación local

En macOS/Python 3.12, la batería de interfaz, recorridos GUI, exportación, informes, robustez y arquitectura terminó con 212 aprobadas y 4 omitidas. Los dos avisos proceden del caso existente de granos con todos sus valores NaN. La comprobación posterior de JKR y sus rechazos explícitos terminó con 11 aprobadas. El análisis de tipos y el lint se ejecutaron sobre los cambios. Estos resultados describen las pruebas locales ejecutadas.
