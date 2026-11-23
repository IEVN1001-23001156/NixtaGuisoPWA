import { Component, inject } from '@angular/core';

import { AvisosService } from '../../servicios/avisos.service';

@Component({
  selector: 'app-avisos',
  templateUrl: './avisos.html'
})
export class Avisos {
  servicio = inject(AvisosService);
}
