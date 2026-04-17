/* =============================================================================
 * qkd_ns3_simulation.cc
 *
 * Real NS-3 C++ simulation for Hybrid QKD + TLS communication stack.
 *
 * Models:
 *   - Quantum channel via P2P link with configurable error/loss rates
 *   - Classical channel for TLS handshake and data transfer
 *   - Eavesdropper (Eve) as a middle node with packet interception
 *   - FlowMonitor for real per-flow metrics
 *   - Bulk data transfer + UDP echo for QKD photon bursts
 *
 * Scenarios (--scenario=<name>):
 *   fiber_10km       Short metro fiber (10 km)
 *   fiber_50km       Intercity fiber (50 km)
 *   fiber_100km      Long fiber (100 km)
 *   satellite_leo    LEO satellite free-space (600 km)
 *   eve_attack       Eavesdropper intercept-resend attack
 *   distance_sweep   Sweep 1-200 km and output CSV
 *   tls_handshake    TLS handshake timing analysis
 *
 * Output: CSV written to --output=<path>
 * ============================================================================= */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/error-model.h"
#include "ns3/packet-sink.h"
#include "ns3/packet-sink-helper.h"
#include "ns3/bulk-send-helper.h"
#include "ns3/udp-echo-helper.h"

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("QKDNs3Simulation");

// ---------------------------------------------------------------------------
// Helpers: QKD physics mapped to NS-3 channel parameters
// ---------------------------------------------------------------------------

/// Fiber attenuation constant (dB/km), standard telecom SMF-28
static const double FIBER_ATTENUATION_DB_PER_KM = 0.2;
/// Speed of light in fiber (m/s), n≈1.5
static const double C_FIBER_MS = 2e8 * 1e-3;  // km/ms → 200 km/ms

/**
 * Compute transmission probability after fiber loss.
 *   T = 10^(-alpha * L / 10) * eta_det
 */
double
FiberTransmission(double distance_km, double attn_db_km = FIBER_ATTENUATION_DB_PER_KM,
                  double eta_det = 0.10)
{
    double loss_db = attn_db_km * distance_km;
    return std::pow(10.0, -loss_db / 10.0) * eta_det;
}

/**
 * Compute expected QBER from depolarization alone.
 *   depolar_prob = 1 - exp(-0.01 * L)
 *   QBER ≈ depolar_prob / 2
 */
double
ExpectedQBER(double distance_km)
{
    double depolar = 1.0 - std::exp(-0.01 * distance_km);
    return std::min(depolar / 2.0, 0.5);
}

/**
 * Compute QBER with Eve's intercept-resend attack.
 *   Eve adds ~25% * intercept_rate additional QBER
 */
double
EveQBER(double distance_km, double intercept_rate)
{
    double base = ExpectedQBER(distance_km);
    double eve  = intercept_rate * 0.25;
    return std::min(base + eve - base * eve, 0.5);
}

/**
 * Secure key rate per pulse (BB84 simplified):
 *   R = 0.5 * Q * max(0, 1 - 2*h(e))
 * where h(e) = binary entropy, Q = detection probability
 */
double
KeyRatePerPulse(double distance_km)
{
    double Q = FiberTransmission(distance_km);
    double e = ExpectedQBER(distance_km);
    if (Q <= 0.0 || e >= 0.11)
        return 0.0;
    double h_e = (e <= 0 || e >= 1)
                     ? 0.0
                     : -e * std::log2(e) - (1.0 - e) * std::log2(1.0 - e);
    return 0.5 * Q * std::max(0.0, 1.0 - 2.0 * h_e);
}

/**
 * Free-space satellite attenuation (much lower than fiber).
 * Approx 10 dB total over 600 km uplink.
 */
double
SatelliteTransmission(double distance_km)
{
    double attn_db_km = 10.0 / 600.0;  // ~0.0167 dB/km
    return FiberTransmission(distance_km, attn_db_km, 0.15);
}

// ---------------------------------------------------------------------------
// CSV output helper
// ---------------------------------------------------------------------------

struct SimResult
{
    std::string scenario;
    double distance_km;
    double qber;
    double key_rate;
    double tx_probability;
    bool eve_present;
    double eve_intercept_rate;
    bool is_secure;

    // FlowMonitor stats
    double throughput_mbps;
    double avg_delay_ms;
    double packet_loss_rate;
    uint64_t total_packets_sent;
    uint64_t total_packets_recv;
    double jitter_ms;

    // TLS timing (ms)
    double tls_handshake_ms;
    double tls_data_transfer_ms;
};

void
WriteCSV(const std::string& path, const std::vector<SimResult>& results)
{
    std::ofstream f(path);
    if (!f.is_open())
    {
        std::cerr << "ERROR: Cannot open output file: " << path << "\n";
        return;
    }

    f << "scenario,distance_km,qber,key_rate,tx_prob,eve_present,intercept_rate,"
         "is_secure,throughput_mbps,avg_delay_ms,packet_loss_rate,"
         "packets_sent,packets_recv,jitter_ms,tls_handshake_ms,tls_data_transfer_ms\n";

    for (const auto& r : results)
    {
        f << std::fixed << std::setprecision(8) << r.scenario << "," << r.distance_km << ","
          << r.qber << "," << r.key_rate << "," << r.tx_probability << ","
          << (r.eve_present ? 1 : 0) << "," << r.eve_intercept_rate << ","
          << (r.is_secure ? 1 : 0) << "," << std::setprecision(4) << r.throughput_mbps << ","
          << r.avg_delay_ms << "," << r.packet_loss_rate << "," << r.total_packets_sent << ","
          << r.total_packets_recv << "," << r.jitter_ms << "," << r.tls_handshake_ms << ","
          << r.tls_data_transfer_ms << "\n";
    }

    f.close();
    std::cout << "[NS-3] Results written to: " << path << "\n";
}

// ---------------------------------------------------------------------------
// Per-scenario simulation runner
// ---------------------------------------------------------------------------

/**
 * Run a point-to-point QKD+TLS simulation for given parameters.
 * Returns a filled SimResult struct.
 */
SimResult
RunSimulation(const std::string& scenario,
              double distance_km,
              double bandwidth_mbps,
              bool eve_present,
              double eve_intercept_rate,
              double sim_duration_s,
              bool is_satellite = false)
{
    SimResult result;
    result.scenario          = scenario;
    result.distance_km       = distance_km;
    result.eve_present       = eve_present;
    result.eve_intercept_rate = eve_present ? eve_intercept_rate : 0.0;

    // ------------------------------------------------------------------
    // Physics calculations
    // ------------------------------------------------------------------
    double tx_prob  = is_satellite ? SatelliteTransmission(distance_km)
                                   : FiberTransmission(distance_km);
    double qber     = eve_present ? EveQBER(distance_km, eve_intercept_rate)
                                  : ExpectedQBER(distance_km);
    double key_rate = KeyRatePerPulse(distance_km);
    if (eve_present)
    {
        // Key rate collapses when QBER >= 11%
        key_rate = (qber < 0.11) ? key_rate * (1.0 - eve_intercept_rate) : 0.0;
    }

    result.qber            = qber;
    result.key_rate        = key_rate;
    result.tx_probability  = tx_prob;
    result.is_secure       = (qber < 0.11) && (key_rate > 0.0);

    // ------------------------------------------------------------------
    // NS-3 topology: Alice ─── [quantum/classical P2P] ─── Bob
    //                (optionally: Alice ── Eve ── Bob)
    // ------------------------------------------------------------------
    NodeContainer nodes;
    int num_nodes = eve_present ? 3 : 2;
    nodes.Create(num_nodes);

    // Propagation delay from distance (fiber: 5 µs/km)
    double delay_ms = distance_km / C_FIBER_MS;
    std::ostringstream delay_str;
    delay_str << std::fixed << std::setprecision(4) << delay_ms << "ms";

    std::ostringstream bw_str;
    bw_str << std::fixed << std::setprecision(0) << bandwidth_mbps << "Mbps";

    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue(bw_str.str()));
    p2p.SetChannelAttribute("Delay", StringValue(delay_str.str()));

    // Packet error rate to model QBER / photon loss
    // Classical channel gets 0.1% loss (realistic TCP/IP)
    // Quantum channel loss modeled via key_rate (physics level)
    double classical_per = 0.001;

    Ptr<RateErrorModel> em = CreateObject<RateErrorModel>();
    em->SetAttribute("ErrorRate", DoubleValue(classical_per));
    em->SetAttribute("ErrorUnit", StringValue("ERROR_UNIT_PACKET"));

    NetDeviceContainer devs;
    if (!eve_present)
    {
        // Alice ── Bob
        devs = p2p.Install(nodes.Get(0), nodes.Get(1));
        nodes.Get(1)->GetDevice(0)->SetAttribute("ReceiveErrorModel", PointerValue(em));
    }
    else
    {
        // Alice ── Eve ── Bob
        // Split distance: Alice-Eve = 50%, Eve-Bob = 50%
        double half_delay   = delay_ms / 2.0;
        double half_dist_km = distance_km / 2.0;
        (void)half_dist_km;

        std::ostringstream hd;
        hd << std::fixed << std::setprecision(4) << half_delay << "ms";

        PointToPointHelper p2p_half;
        p2p_half.SetDeviceAttribute("DataRate", StringValue(bw_str.str()));
        p2p_half.SetChannelAttribute("Delay", StringValue(hd.str()));

        // Eve's interception modeled as higher error rate on Alice→Eve segment
        double eve_per = eve_intercept_rate * 0.25 + 0.001;
        Ptr<RateErrorModel> eve_em = CreateObject<RateErrorModel>();
        eve_em->SetAttribute("ErrorRate", DoubleValue(eve_per));
        eve_em->SetAttribute("ErrorUnit", StringValue("ERROR_UNIT_PACKET"));

        NetDeviceContainer de1 = p2p_half.Install(nodes.Get(0), nodes.Get(1));  // Alice-Eve
        NetDeviceContainer de2 = p2p_half.Install(nodes.Get(1), nodes.Get(2));  // Eve-Bob
        de1.Get(1)->SetAttribute("ReceiveErrorModel", PointerValue(eve_em));
        de2.Get(1)->SetAttribute("ReceiveErrorModel", PointerValue(em));

        for (uint32_t i = 0; i < de1.GetN(); i++)
            devs.Add(de1.Get(i));
        for (uint32_t i = 0; i < de2.GetN(); i++)
            devs.Add(de2.Get(i));
    }

    // ------------------------------------------------------------------
    // Internet stack
    // ------------------------------------------------------------------
    InternetStackHelper internet;
    internet.Install(nodes);

    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.1.0", "255.255.255.0");

    Ipv4InterfaceContainer ifaces;
    if (!eve_present)
    {
        ifaces = ipv4.Assign(devs);
    }
    else
    {
        // Assign two subnets
        NetDeviceContainer sub1, sub2;
        sub1.Add(devs.Get(0));
        sub1.Add(devs.Get(1));
        sub2.Add(devs.Get(2));
        sub2.Add(devs.Get(3));

        ipv4.SetBase("10.1.1.0", "255.255.255.0");
        Ipv4InterfaceContainer i1 = ipv4.Assign(sub1);
        ipv4.SetBase("10.1.2.0", "255.255.255.0");
        Ipv4InterfaceContainer i2 = ipv4.Assign(sub2);

        for (uint32_t j = 0; j < i1.GetN(); j++)
            ifaces.Add(i1.Get(j));
        for (uint32_t j = 0; j < i2.GetN(); j++)
            ifaces.Add(i2.Get(j));

        Ipv4GlobalRoutingHelper::PopulateRoutingTables();
    }

    // ------------------------------------------------------------------
    // Applications
    //
    //  Port 9:  BulkSend (TCP) — models Classical TLS data channel
    //  Port 10: UdpEcho        — models QKD photon exchange (sifting messages)
    // ------------------------------------------------------------------
    uint16_t tcp_port = 9;
    uint16_t udp_port = 10;

    // Bob node index (node 2 when Eve is present, node 1 otherwise)
    // bob_iface_idx is different: ifaces is built from i1(Alice,Eve-A) + i2(Eve-B,Bob)
    // so Bob's IP is at position 3 in the combined container when eve_present.
    int bob_node_idx  = eve_present ? 2 : 1;
    int bob_iface_idx = eve_present ? 3 : 1;
    Ipv4Address bob_addr = ifaces.GetAddress(bob_iface_idx);

    // --- TCP BulkSend (Alice → Bob) ---
    BulkSendHelper bulk("ns3::TcpSocketFactory",
                        InetSocketAddress(bob_addr, tcp_port));
    bulk.SetAttribute("MaxBytes", UintegerValue(0));  // unlimited
    ApplicationContainer src_apps = bulk.Install(nodes.Get(0));
    src_apps.Start(Seconds(0.5));
    src_apps.Stop(Seconds(sim_duration_s - 0.5));

    PacketSinkHelper sink("ns3::TcpSocketFactory",
                          InetSocketAddress(Ipv4Address::GetAny(), tcp_port));
    ApplicationContainer sink_apps = sink.Install(nodes.Get(bob_node_idx));
    sink_apps.Start(Seconds(0.1));
    sink_apps.Stop(Seconds(sim_duration_s));

    // --- UDP Echo (QKD sifting channel) ---
    UdpEchoServerHelper echo_server(udp_port);
    ApplicationContainer server_apps = echo_server.Install(nodes.Get(bob_node_idx));
    server_apps.Start(Seconds(0.1));
    server_apps.Stop(Seconds(sim_duration_s));

    UdpEchoClientHelper echo_client(bob_addr, udp_port);
    echo_client.SetAttribute("MaxPackets", UintegerValue(10000));
    echo_client.SetAttribute("Interval", TimeValue(MilliSeconds(1)));
    echo_client.SetAttribute("PacketSize", UintegerValue(128));
    ApplicationContainer client_apps = echo_client.Install(nodes.Get(0));
    client_apps.Start(Seconds(0.5));
    client_apps.Stop(Seconds(sim_duration_s - 0.5));

    // ------------------------------------------------------------------
    // FlowMonitor — captures real per-flow metrics
    // ------------------------------------------------------------------
    FlowMonitorHelper fm_helper;
    Ptr<FlowMonitor> monitor = fm_helper.InstallAll();

    // ------------------------------------------------------------------
    // Run simulation
    // ------------------------------------------------------------------
    Simulator::Stop(Seconds(sim_duration_s));
    Simulator::Run();

    // ------------------------------------------------------------------
    // Collect FlowMonitor statistics
    // ------------------------------------------------------------------
    monitor->CheckForLostPackets();
    Ptr<Ipv4FlowClassifier> classifier =
        DynamicCast<Ipv4FlowClassifier>(fm_helper.GetClassifier());
    FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats();

    double total_throughput_bps = 0.0;
    double total_delay_s        = 0.0;
    double total_jitter_s       = 0.0;
    uint64_t total_sent         = 0;
    uint64_t total_recv         = 0;
    uint64_t total_lost         = 0;
    int flow_count              = 0;

    for (auto& kv : stats)
    {
        FlowMonitor::FlowStats fs = kv.second;
        if (fs.rxPackets == 0)
            continue;

        double dur_s = fs.timeLastRxPacket.GetSeconds() - fs.timeFirstTxPacket.GetSeconds();
        if (dur_s <= 0)
            continue;

        double throughput = fs.rxBytes * 8.0 / dur_s;
        total_throughput_bps += throughput;
        total_delay_s += fs.delaySum.GetSeconds() / fs.rxPackets;
        total_jitter_s += fs.jitterSum.GetSeconds() / std::max((uint32_t)1, fs.rxPackets - 1);
        total_sent += fs.txPackets;
        total_recv += fs.rxPackets;
        total_lost += fs.lostPackets;
        flow_count++;
    }

    if (flow_count > 0)
    {
        result.throughput_mbps   = total_throughput_bps / flow_count / 1e6;
        result.avg_delay_ms      = (total_delay_s / flow_count) * 1000.0;
        result.jitter_ms         = (total_jitter_s / flow_count) * 1000.0;
        result.total_packets_sent = total_sent;
        result.total_packets_recv = total_recv;
        result.packet_loss_rate  = total_lost / std::max((double)total_sent, 1.0);
    }
    else
    {
        result.throughput_mbps   = 0;
        result.avg_delay_ms      = delay_ms;
        result.jitter_ms         = 0;
        result.total_packets_sent = 0;
        result.total_packets_recv = 0;
        result.packet_loss_rate  = 1.0;
    }

    // TLS timing: measured RTT (from FlowMonitor) + crypto overhead
    // Use FlowMonitor avg one-way delay as RTT base; fall back to theoretical if
    // no flows were observed (e.g. very short simulation or total packet loss).
    double rtt_ms = (result.avg_delay_ms > 0)
                        ? result.avg_delay_ms * 2.0  // FlowMonitor measured RTT
                        : 2.0 * delay_ms;            // fallback: theoretical propagation

    // Crypto overhead (ms) — estimated from Python tls/ implementation benchmarks:
    //   X25519 ECDH:     ~0.10 ms
    //   ML-KEM-768:      ~2.00 ms  (keygen + encapsulate)
    //   QKD key inject:  ~0.05 ms
    //   HKDF-SHA256:     ~0.05 ms
    double ecdh_ms   = 0.10;
    double mlkem_ms  = 2.00;
    double qkd_ms    = 0.05;
    double hkdf_ms   = 0.05;
    double crypto_ms = 2.0 * (ecdh_ms + mlkem_ms + qkd_ms + hkdf_ms);

    // 3 network round trips during handshake
    result.tls_handshake_ms     = 3.0 * rtt_ms + crypto_ms;
    // Data transfer: 10 KB over channel
    result.tls_data_transfer_ms = (10000.0 * 8.0) / (bandwidth_mbps * 1e6) * 1000.0 + delay_ms;

    Simulator::Destroy();

    return result;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

int
main(int argc, char* argv[])
{
    // -----------------------------------------------------------------------
    // Command-line arguments
    // -----------------------------------------------------------------------
    std::string scenario        = "fiber_10km";
    std::string output_path     = "qkd_results.csv";
    double distance_km          = 10.0;
    double bandwidth_mbps       = 1000.0;
    double eve_intercept_rate   = 0.0;
    double sim_duration_s       = 5.0;
    bool verbose                = false;

    CommandLine cmd(__FILE__);
    cmd.AddValue("scenario",      "Scenario name (fiber_10km|fiber_50km|fiber_100km|satellite_leo|eve_attack|distance_sweep|tls_handshake)", scenario);
    cmd.AddValue("output",        "path CSV output file", output_path);
    cmd.AddValue("distance",      "Distance in km (used when scenario=custom)", distance_km);
    cmd.AddValue("bandwidth",     "Link bandwidth in Mbps", bandwidth_mbps);
    cmd.AddValue("intercept",     "Eve intercept rate (0.0-1.0, for eve_attack)", eve_intercept_rate);
    cmd.AddValue("duration",      "Simulation duration in seconds", sim_duration_s);
    cmd.AddValue("verbose",       "Enable NS-3 logging", verbose);
    cmd.Parse(argc, argv);

    if (verbose)
    {
        LogComponentEnable("QKDNs3Simulation", LOG_LEVEL_INFO);
    }

    std::cout << "[NS-3] QKD Simulation Starting\n";
    std::cout << "[NS-3] Scenario : " << scenario << "\n";
    std::cout << "[NS-3] Output   : " << output_path << "\n\n";

    std::vector<SimResult> results;

    // -----------------------------------------------------------------------
    // Scenario dispatch
    // -----------------------------------------------------------------------

    if (scenario == "fiber_10km")
    {
        std::cout << "[NS-3] Running: Metro Fiber 10 km\n";
        results.push_back(RunSimulation("fiber_10km", 10.0, bandwidth_mbps, false, 0.0, sim_duration_s));
    }
    else if (scenario == "fiber_50km")
    {
        std::cout << "[NS-3] Running: Intercity Fiber 50 km\n";
        results.push_back(RunSimulation("fiber_50km", 50.0, bandwidth_mbps, false, 0.0, sim_duration_s));
    }
    else if (scenario == "fiber_100km")
    {
        std::cout << "[NS-3] Running: Long Fiber 100 km\n";
        results.push_back(RunSimulation("fiber_100km", 100.0, bandwidth_mbps, false, 0.0, sim_duration_s));
    }
    else if (scenario == "satellite_leo")
    {
        std::cout << "[NS-3] Running: LEO Satellite 600 km\n";
        results.push_back(RunSimulation("satellite_leo", 600.0, 100.0, false, 0.0, sim_duration_s, true));
    }
    else if (scenario == "eve_attack")
    {
        std::cout << "[NS-3] Running: Eve Attack Scenario\n";
        // Sweep intercept rates
        std::vector<double> rates = {0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0};
        for (double rate : rates)
        {
            std::cout << "[NS-3]   intercept_rate=" << rate << "\n";
            results.push_back(RunSimulation("eve_attack", distance_km > 10.0 ? distance_km : 20.0,
                                            bandwidth_mbps, true, rate, sim_duration_s));
        }
    }
    else if (scenario == "distance_sweep")
    {
        std::cout << "[NS-3] Running: Distance Sweep\n";
        std::vector<double> distances = {1, 5, 10, 20, 30, 50, 75, 100, 150, 200};
        for (double d : distances)
        {
            std::cout << "[NS-3]   distance=" << d << " km\n";
            results.push_back(RunSimulation("distance_sweep", d, bandwidth_mbps, false, 0.0,
                                            std::min(sim_duration_s, 3.0)));
        }
    }
    else if (scenario == "tls_handshake")
    {
        std::cout << "[NS-3] Running: TLS Handshake Analysis\n";
        std::vector<double> distances = {1, 10, 50, 100};
        for (double d : distances)
        {
            std::cout << "[NS-3]   distance=" << d << " km\n";
            results.push_back(RunSimulation("tls_handshake_" + std::to_string((int)d) + "km", d,
                                            bandwidth_mbps, false, 0.0, sim_duration_s));
        }
    }
    else if (scenario == "custom")
    {
        std::cout << "[NS-3] Running: Custom Scenario (" << distance_km << " km)\n";
        results.push_back(RunSimulation("custom", distance_km, bandwidth_mbps,
                                        eve_intercept_rate > 0.0, eve_intercept_rate,
                                        sim_duration_s));
    }
    else
    {
        std::cerr << "[NS-3] ERROR: Unknown scenario '" << scenario << "'\n";
        std::cerr << "       Valid: fiber_10km, fiber_50km, fiber_100km, satellite_leo,\n";
        std::cerr << "              eve_attack, distance_sweep, tls_handshake, custom\n";
        return 1;
    }

    // -----------------------------------------------------------------------
    // Print summary table
    // -----------------------------------------------------------------------
    std::cout << "\n[NS-3] ======================================================\n";
    std::cout << "[NS-3]  Simulation Results\n";
    std::cout << "[NS-3] ======================================================\n";
    std::cout << std::fixed << std::setprecision(4);
    std::cout << std::left
              << std::setw(22) << "Scenario"
              << std::setw(10) << "Dist(km)"
              << std::setw(10) << "QBER"
              << std::setw(14) << "KeyRate"
              << std::setw(10) << "Secure"
              << std::setw(14) << "Throughput"
              << std::setw(12) << "Delay(ms)"
              << "\n";
    std::cout << std::string(92, '-') << "\n";

    for (const auto& r : results)
    {
        std::cout << std::left
                  << std::setw(22) << r.scenario
                  << std::setw(10) << r.distance_km
                  << std::setw(10) << r.qber
                  << std::setw(14) << r.key_rate
                  << std::setw(10) << (r.is_secure ? "YES" : "NO")
                  << std::setw(14) << r.throughput_mbps
                  << std::setw(12) << r.avg_delay_ms
                  << "\n";
    }

    // -----------------------------------------------------------------------
    // Write CSV
    // -----------------------------------------------------------------------
    WriteCSV(output_path, results);

    std::cout << "\n[NS-3] Done. " << results.size() << " scenario(s) completed.\n";
    return 0;
}
