#!/usr/bin/env python3
import os
import time
from dotenv import load_dotenv
import pyautogui
from windsurf_controller import map_ready_pixel_xy, _measure_ready_pixel_rgb, _rgb_at


def sample_once():
    rp_x = int(os.getenv('READY_PIXEL_X', '-1'))
    rp_y = int(os.getenv('READY_PIXEL_Y', '-1'))
    rp_r = int(os.getenv('READY_PIXEL_R', '0'))
    rp_g = int(os.getenv('READY_PIXEL_G', '0'))
    rp_b = int(os.getenv('READY_PIXEL_B', '0'))
    rp_tol = int(os.getenv('READY_PIXEL_TOL', '8'))
    rp_tol_pct = float(os.getenv('READY_PIXEL_TOL_PCT', '-1'))
    rp_mode = os.getenv('READY_PIXEL_COORD_MODE', 'top').strip().lower()
    rp_dx = int(os.getenv('READY_PIXEL_DX', '0'))
    rp_dy = int(os.getenv('READY_PIXEL_DY', '0'))

    if rp_x < 0 or rp_y < 0:
        return {'err': 'READY_PIXEL not configured'}

    sx, sy = map_ready_pixel_xy(rp_x, rp_y, rp_mode, rp_dx, rp_dy)
    # Консистентная выборка (как в color_pipette / windsurf_controller) с авто-выбором источника
    avg_k = int(os.getenv('READY_PIXEL_AVG_K', '3'))
    (pr, pg, pb), used_src = _measure_ready_pixel_rgb(int(sx), int(sy), max(1, avg_k), (rp_r, rp_g, rp_b))
    # Параллельно измерим "direct 1x1" для сравнения
    dr1, dg1, db1 = _rgb_at(int(sx), int(sy))
    dr, dg, db = abs(int(pr) - rp_r), abs(int(pg) - rp_g), abs(int(pb) - rp_b)
    if rp_tol_pct is not None and rp_tol_pct >= 0:
        rel = (dr + dg + db) / (3.0 * 255.0) * 100.0
        match = rel <= rp_tol_pct
    else:
        match = (dr <= rp_tol and dg <= rp_tol and db <= rp_tol)
    return {
        'used_xy': (sx, sy),
        'actual': (int(pr), int(pg), int(pb)),
        'src': used_src,
        'target': (rp_r, rp_g, rp_b),
        'direct': (int(dr1), int(dg1), int(db1)),
        'delta': (dr, dg, db),
        'tol': rp_tol,
        'tol_pct': rp_tol_pct,
        'match': match,
        'mode': rp_mode,
        'dxdy': (rp_dx, rp_dy),
    }


def main():
    load_dotenv(override=True)
    end = time.time() + 10
    print('READY_PIXEL simple test (10s). Move nothing, just observe:')
    while time.time() < end:
        try:
            s = sample_once()
            if 'err' in s:
                print('ERR:', s['err'])
                break
            print(
                f"used_xy={s['used_xy']} mode={s['mode']} src={s['src']} actual={s['actual']} target={s['target']} "
                f"direct={s['direct']} delta={s['delta']} tol={s['tol']} tol_pct={s['tol_pct']} match={s['match']}"
            )
        except Exception as e:
            print('err:', e)
        time.sleep(0.5)
    print('Done')


if __name__ == '__main__':
    main()
