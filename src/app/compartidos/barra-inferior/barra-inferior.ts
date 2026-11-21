import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  imports: [RouterLink, RouterLinkActive],
  selector: 'app-barra-inferior',
  styleUrl: './barra-inferior.css',
  templateUrl: './barra-inferior.html',
})
export class BarraInferior {}