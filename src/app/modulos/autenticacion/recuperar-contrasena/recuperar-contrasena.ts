import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  imports: [RouterLink],
  selector: 'app-recuperar-contrasena',
  styleUrl: './recuperar-contrasena.css',
  templateUrl: './recuperar-contrasena.html',
})
export class RecuperarContrasena {
  codigoEnviado = false;

  mandarCodigo(event: Event): void {
    event.preventDefault();
    this.codigoEnviado = true;
  }
}