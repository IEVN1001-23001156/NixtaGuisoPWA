import { Component, inject, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AuthRolService } from './servicios/auth-rol.service';

@Component({
  imports: [RouterOutlet],
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