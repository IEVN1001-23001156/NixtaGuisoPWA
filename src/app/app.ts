import { Component, inject, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { Avisos } from './panel/componentes/avisos/avisos';
import { AuthRolService } from './servicios/auth-rol.service';

@Component({
  imports: [RouterOutlet, Avisos],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly authRol = inject(AuthRolService);

  async ngOnInit(): Promise<void> {
    await this.authRol.consultarSesionActual();
  }
}