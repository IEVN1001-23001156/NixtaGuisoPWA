// Forma general de las respuestas de Flask: { "exito": true, "mensaje": "..." }
export interface Respuesta {
  exito: boolean;
  mensaje?: string;
}
