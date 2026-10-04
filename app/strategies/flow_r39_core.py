"""Nexvory FLOW M1 independente para DERIV DEMO.

A estrategia monta seu proprio universo de ativos e candles M1 pelo BrokerAdapter.
Nao depende de radar, monitor, pre-decisao ou selecao de outro operacional.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import functools
import json
import math
import os
import queue
import statistics
import threading
import time

VERSAO = 'FLOW_M1_INDEPENDENTE_DEMO_R39_20261003'


def _num(v):
    try:
        n = float(v)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _barra(epoch, preco):
    return {'epoch': epoch, 'open': preco, 'high': preco, 'low': preco,
            'close': preco, 'ticks': 1, 'caminho': 0.0, 'ultimo': preco}


def _update(bar, preco):
    bar['caminho'] += abs(preco - bar['ultimo'])
    bar['ultimo'] = preco
    bar['high'] = max(bar['high'], preco)
    bar['low'] = min(bar['low'], preco)
    bar['close'] = preco
    bar['ticks'] += 1


def _body(c):
    return abs(c['close']-c['open']) / max(c['high']-c['low'], 1e-20)


def _extremo(c, direcao):
    r = c['high']-c['low']
    if r <= 0:
        return 0.
    return (c['close']-c['low'])/r if direcao=='CALL' else (c['high']-c['close'])/r


def _mov(c, direcao):
    return c['close']-c['open'] if direcao=='CALL' else c['open']-c['close']


@dataclass(frozen=True)
class Parametros:
    min_tamanho_base: int = 20
    min_ticks_candle: int = 3
    corpo_impulso_min: float = .60
    fechamento_extremo_min: float = .70
    correção_max: float = .40
    corpo_correcao_max_mediana: float = .70
    eficiencia_min: float = .48
    extensao_max_mediana: float = 4.0
    buffer_rompimento: float = .03
    dist_entrada_max_mediana: float = .22
    volatilidade_max_multiplo: float = 2.8
    janela_inicio_s: int = 5
    janela_fim_s: int = 18
    confirmar_ticks: int = 3
    confirmar_min_segundos: int = 1
    confirmar_max_segundos: int = 4
    atraso_desfecho_max_s: int = 4


class FlowMotor:
    """Apenas calculos em memoria; um motor por simbolo, instancia nao compartilhada."""
    def __init__(self, simbolo, cfg=None):
        self.simbolo = simbolo
        self.cfg = cfg or Parametros()
        self.fechados = deque(maxlen=125)
        self.atual = None
        self.ultimo_epoch = None
        self.ultima_setup = None
        self.breakout = None
        self.terminal_candle = None
        self.pendentes = []
        self.indicadores = defaultdict(int)

    def _m5(self, epoch_minuto, candle_vivo):
        """Somente M1 contiguos e fechados; M5 em andamento inclui tick atual."""
        historico = list(self.fechados)
        inicio_atual = (epoch_minuto // 300) * 300
        grupos = defaultdict(list)
        for c in historico:
            grupos[(c['epoch']//300)*300].append(c)
        completos = []
        for ep, vs in sorted(grupos.items()):
            vs.sort(key=lambda v:v['epoch'])
            if (ep < inicio_atual and len(vs)==5 and
                    [v['epoch'] for v in vs]==list(range(ep,ep+300,60))):
                completos.append({'epoch':ep,'open':vs[0]['open'],
                                  'high':max(v['high'] for v in vs),
                                  'low':min(v['low'] for v in vs),
                                  'close':vs[-1]['close']})
        if len(completos) < 5:
            return {'motivo':'M5_WARMUP_INSUFICIENTE', 'm5_completos':len(completos)}
        if inicio_atual - (completos[-1]['epoch']+300)>720:
            return {'motivo':'M5_BASE_DESATUALIZADA'}
        medias = [x['high']-x['low'] for x in completos[-5:]]
        mediana = statistics.median(medias)
        if mediana <= 0:
            return {'motivo':'M5_MEDIANA_ZERO'}
        corrente = sorted((c for c in historico if inicio_atual <= c['epoch'] < epoch_minuto),key=lambda c:c['epoch'])
        exp = list(range(inicio_atual, epoch_minuto, 60))
        if [c['epoch'] for c in corrente] != exp:
            return {'motivo':'M5_M1_DESCONTINUO'}
        corrente = corrente + [candle_vivo]
        vivo = {'epoch':inicio_atual,'open':corrente[0]['open'],
                'high':max(c['high'] for c in corrente),
                'low':min(c['low'] for c in corrente),
                'close':candle_vivo['close']}
        return {'motivo':None,'anterior':completos[-1], 'vivo':vivo,
                'mediana':mediana,'decorrido':self.ultimo_epoch-inicio_atual}

    def _setup(self, epoch_minuto, candle_vivo):
        h = list(self.fechados)
        if len(h) < self.cfg.min_tamanho_base + 4:
            return None, 'M1_WARMUP_INSUFICIENTE'
        if candle_vivo['ticks'] < 1:
            return None, 'SEM_TICKS'
        cand = []
        for direcao in ('CALL','PUT'):
            for n_corr in (2,1):
                n = n_corr + 2
                padrao = h[-n:]
                if len(padrao) != n or [x['epoch'] for x in padrao] != list(range(epoch_minuto-60*n,epoch_minuto,60)):
                    continue
                base = h[-n-self.cfg.min_tamanho_base:-n]
                if len(base)<self.cfg.min_tamanho_base or [x['epoch'] for x in base] != list(range(epoch_minuto-60*(n+self.cfg.min_tamanho_base),epoch_minuto-60*n,60)):
                    continue
                medidas = [c['high']-c['low'] for c in base]
                mediana = statistics.median(medidas)
                if mediana <= 0:
                    continue
                p1,p2 = padrao[:2]
                correcoes = padrao[2:]
                if any(_mov(p,direcao)<=0 or _body(p)<self.cfg.corpo_impulso_min
                       or _extremo(p,direcao)<self.cfg.fechamento_extremo_min
                       or p['ticks']<self.cfg.min_ticks_candle for p in (p1,p2)):
                    continue
                if any(p['high']-p['low']>mediana*self.cfg.volatilidade_max_multiplo for p in (p1,p2)):
                    continue
                if (direcao=='CALL' and p2['close']<=p1['close']) or (direcao=='PUT' and p2['close']>=p1['close']):
                    continue
                if any(_mov(c,direcao)>=0 or abs(c['close']-c['open'])>mediana*self.cfg.corpo_correcao_max_mediana
                       or c['ticks']<self.cfg.min_ticks_candle for c in correcoes):
                    continue
                impulso = (p2['close']-p1['open']) if direcao=='CALL' else (p1['open']-p2['close'])
                if impulso<mediana*.9 or impulso>mediana*self.cfg.extensao_max_mediana:
                    continue
                profundidade = ((p2['close'] - min(c['low'] for c in correcoes)) if direcao=='CALL'
                                else (max(c['high'] for c in correcoes)-p2['close']))/impulso
                if profundidade<.025 or profundidade>self.cfg.correção_max:
                    continue
                eficiencia = impulso / max(sum(c['caminho'] for c in (p1,p2)), 1e-20)
                if eficiencia < self.cfg.eficiencia_min:
                    continue
                if n_corr==2 and abs(correcoes[-1]['close']-correcoes[-1]['open'])>abs(correcoes[0]['close']-correcoes[0]['open'])*1.1:
                    continue
                nivel = (max(c['high'] for c in correcoes) if direcao=='CALL'
                         else min(c['low'] for c in correcoes))
                limiar = nivel + mediana*self.cfg.buffer_rompimento*(1 if direcao=='CALL' else -1)
                cand.append({'direcao':direcao,'n_corr':n_corr,'mediana':mediana,
                             'nivel':nivel,'limiar':limiar,'profundidade':round(profundidade,4),
                             'eficiencia':round(eficiencia,4),'impulso_mediana':round(impulso/mediana,4)})
        if not cand:
            return None, 'SEM_FORMACAO'
        # Prefere duas velas de correcao quando ambas satisfazem o padrao.
        cand.sort(key=lambda c:-c['n_corr'])
        return cand[0], None

    def _filtro_m5(self, setup, epoch_minuto, candle_vivo):
        contexto = self._m5(epoch_minuto,candle_vivo)
        if contexto['motivo']:
            # R37: M5 é apenas veto adicional quando existe contexto válido.
            # Falta de warmup/base M5 não pode bloquear uma estratégia M1.
            return None, {'m5_disponivel':False,
                          'motivo_diagnostico':contexto['motivo'],
                          'contexto':contexto}
        direcao=setup['direcao']; med=contexto['mediana']
        for tipo, c in (('FECHADO',contexto['anterior']),('AO_VIVO',contexto['vivo'])):
            if tipo=='AO_VIVO' and contexto['decorrido']<90:
                continue
            movimento=_mov(c,direcao)
            if (movimento<0 and _body(c)>=.70
                    and _extremo(c,'PUT' if direcao=='CALL' else 'CALL')>=.80
                    and c['high']-c['low']>=med*.55):
                return 'M5_FORCA_CONTRA_'+tipo, {'tipo':tipo,'contexto':contexto}
        return None, {'mediana_m5':med,'m5_decorrido':contexto['decorrido']}

    def _registrar_desfechos(self, epoch, preco):
        saida = []
        for s in list(self.pendentes):
            if epoch < s['expira_epoch']:
                continue
            self.pendentes.remove(s)
            atraso = epoch-s['expira_epoch']
            if atraso > self.cfg.atraso_desfecho_max_s:
                status='INDETERMINADO'
            elif preco==s['preco_entrada']:
                status='EMPATE'
            elif ((preco>s['preco_entrada']) == (s['direcao']=='CALL')):
                status='WIN_TEORICO'
            else:
                status='LOSS_TEORICO'
            saida.append({'tipo':'RESULTADO_RECUSA' if s['tipo']=='RECUSADO' else 'RESULTADO',
                          'id':s['id'],'simbolo':self.simbolo,
                          'direcao':s['direcao'],'entrada_epoch':s['entrada_epoch'],
                          'preco_entrada':s['preco_entrada'],'expira_epoch':s['expira_epoch'],
                          'preco_final_observado':preco,'epoch_final_observado':epoch,
                          'atraso_segundos':atraso,'resultado':status,
                          'aviso':'PRECO_OBSERVADO_NAO_E_PRECO_EXECUTADO'})
        return saida

    def on_tick(self, epoch, preco):
        """Retorna eventos auditaveis. NUNCA executa trades nem faz requests."""
        p = _num(preco)
        if p is None or p<=0 or isinstance(epoch,bool):
            self.indicadores['TICK_INVALIDO']+=1; return []
        try:
            ep = int(epoch)
        except (TypeError, ValueError, OverflowError):
            self.indicadores['TICK_INVALIDO']+=1; return []
        if ep<=0 or (self.ultimo_epoch is not None and ep<self.ultimo_epoch):
            self.indicadores['TICK_ATRASADO']+=1; return []
        self.ultimo_epoch=ep
        eventos = self._registrar_desfechos(ep,p)
        minuto=(ep//60)*60
        if self.atual is None:
            self.atual=_barra(minuto,p)
            return eventos
        if minuto!=self.atual['epoch']:
            # M1 sem ticks no meio torna a amostra invalida para o padrao.
            if minuto-self.atual['epoch']!=60:
                self.fechados.clear(); self.indicadores['GAP_M1']+=1
            else:
                self.fechados.append(self.atual)
            self.atual=_barra(minuto,p)
            self.breakout=None
            self.terminal_candle=None
            self.ultima_setup=None
        else:
            _update(self.atual,p)
        segundo=ep-minuto
        # Sem vazamento futuro: o contexto em formacao so ve precos ate este tick.
        if self.terminal_candle==minuto:
            return eventos
        setup,err=self._setup(minuto,self.atual)
        if not setup:
            self.indicadores[err]+=1
            return eventos
        if self.ultima_setup is None:
            self.ultima_setup=setup
            eventos.append({'tipo':'FORMACAO','versao':VERSAO,'simbolo':self.simbolo,
                            'epoch_m1':minuto,'setup':dict(setup)})
        if segundo>self.cfg.janela_fim_s:
            if self.terminal_candle!=minuto:
                eventos.append({'tipo':'RECUSADO','simbolo':self.simbolo,'epoch_m1':minuto,
                                'motivo':'JANELA_ENCERRADA','direcao':setup['direcao']})
                self.terminal_candle=minuto
            return eventos
        if not self.cfg.janela_inicio_s<=segundo<=self.cfg.janela_fim_s:
            return eventos
        direcao=setup['direcao']; limiar=setup['limiar']
        rompimento = p>=limiar if direcao=='CALL' else p<=limiar
        if not rompimento:
            self.breakout=None
            return eventos
        dist = ((p-limiar) if direcao=='CALL' else (limiar-p))/setup['mediana']
        if dist > self.cfg.dist_entrada_max_mediana:
            self.indicadores['PRECO_ESTICADO']+=1
            self.breakout=None
            return eventos
        if not self.breakout or self.breakout['direcao']!=direcao:
            self.breakout={'direcao':direcao,'epoch':ep,'ticks':1,'primeiro':p,'ultimo':p}
            return eventos
        b=self.breakout
        if (p<b['ultimo'] and direcao=='CALL') or (p>b['ultimo'] and direcao=='PUT'):
            self.breakout=None; return eventos
        b['ticks']+=1; b['ultimo']=p
        duracao=ep-b['epoch']
        if duracao>self.cfg.confirmar_max_segundos:
            self.breakout=None; return eventos
        deslocamento=(p-b['primeiro']) if direcao=='CALL' else (b['primeiro']-p)
        if (b['ticks']<self.cfg.confirmar_ticks or duracao<self.cfg.confirmar_min_segundos
                or deslocamento < setup['mediana']*.025):
            return eventos
        veto_m5,contexto=self._filtro_m5(setup,minuto,self.atual)
        sinal_id='%s:%d:%s'%(self.simbolo,ep,direcao)
        if veto_m5:
            self.indicadores[veto_m5]+=1
            recusa={'tipo':'RECUSADO','id':sinal_id,'versao':VERSAO,
                    'simbolo':self.simbolo,'epoch_m1':minuto,
                    'entrada_epoch':ep,'preco_entrada':p,'expira_epoch':ep+60,
                    'direcao':direcao,'motivo':veto_m5,'setup':dict(setup),
                    'contexto_m5':contexto,
                    'observacao':'RECUSA_COM_RESULTADO_CONTRAFACTUAL_SEM_COMPRA'}
            self.pendentes.append(recusa)
            eventos.append(recusa)
        else:
            sinal={'tipo':'SINAL','id':sinal_id,'versao':VERSAO,'simbolo':self.simbolo,
                   'epoch_m1':minuto,'entrada_epoch':ep,'preco_entrada':p,
                   'expira_epoch':ep+60,'direcao':direcao,'setup':dict(setup),
                   'contexto_m5':contexto,'observacao':'SINAL_FLOW_R37_ENCAMINHADO_AO_EXECUTOR_DEMO'}
            self.pendentes.append(sinal)
            self.indicadores['SINAL']+=1
            eventos.append(sinal)
        self.terminal_candle=minuto
        return eventos


