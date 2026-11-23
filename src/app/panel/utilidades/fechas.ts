/**
 * Fechas en la hora LOCAL del navegador (León, Gto.).
 * Importante: no usar new Date().toISOString(), porque da la fecha en hora universal (UTC):
 * a partir de las 6 de la tarde en México ya sería "mañana".
 */
export function hoyLocal(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function mesLocal(): string {
  return hoyLocal().slice(0, 7);
}
